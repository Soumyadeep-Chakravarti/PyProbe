# PyProbe Safety Model

This document defines **when memory mutation is safe** and **when it will corrupt Python's runtime**. This is the intellectual core of PyProbe's Phase 2 (Scalpel) and the key research contribution.

> **READ THIS BEFORE WRITING ANY MUTATION CODE**

---

## The Fundamental Problem

Python assumes its memory is **immutable from the outside**. When we mutate objects directly:

1. We bypass Python's invariant checks
2. We can corrupt shared state
3. We can confuse the garbage collector
4. We can cause segmentation faults

The goal of this safety model is to define **precisely when mutation is safe**.

---

## Safety Classification

We classify objects into three categories:

| Category | Can Mutate? | Examples |
|----------|-------------|----------|
| **NEVER** | No | Interned strings, cached integers, immortal objects |
| **DANGEROUS** | With extreme care | Shared objects (refcount > 1) |
| **SAFE** | Yes | Sole-reference objects |

---

## NEVER Mutate: Absolute Rules

### Rule 1: Never Mutate Interned Strings

```python
a = "hello"
b = "hello"
assert a is b  # Same object!

# If we mutate 'a' in memory, 'b' is also corrupted
# AND every other "hello" in the entire program
```

**Detection**:
```python
def is_interned(addr):
    lens = StringLens.from_address(addr + 16)
    return lens.interned != 0  # 0 = not interned
```

### Rule 2: Never Mutate Cached Small Integers

CPython caches integers from **-5 to 256**:

```python
a = 256
b = 256
assert a is b  # Cached!

a = 257
b = 257
assert a is not b  # Not cached
```

**Detection**:
```python
def is_cached_int(value):
    return -5 <= value <= 256
```

> **Horror Story**: If you mutate the integer `1` to become `2`, every `1` in Python becomes `2`. Loops break. Indexing breaks. Everything breaks.

### Rule 3: Never Mutate Immortal Objects (3.12+)

PEP 683 introduced "immortal" objects that should never be deallocated:

- `None`
- `True` / `False`
- `Ellipsis` (`...`)
- Small integers
- Some internal singletons

**Detection** (3.12+):
```python
def is_immortal(addr):
    refcnt = ctypes.c_ssize_t.from_address(addr).value
    # Immortal objects have a special refcount pattern
    # In 3.12+, this is a very large value
    return refcnt > (1 << 30)  # Approximate check
```

### Rule 4: Never Mutate Type Objects

Type objects (`int`, `str`, `list`, etc.) are deeply integrated into Python's runtime:

```python
# NEVER do this:
# mutate(type(x))  # Corrupts ALL objects of that type
```

### Rule 5: Never Mutate During GC

If the garbage collector is running, memory is in a transitional state. Mutations during GC can cause:

- Dangling pointers
- Double frees
- Infinite loops in cycle detection

**Detection**:
```python
import gc
def is_gc_running():
    return gc.isenabled() and gc.get_count()[0] > 0
    # Note: This is approximate, not foolproof
```

---

## DANGEROUS: Shared Objects

### The Refcount Problem

If `refcount > 1`, multiple references point to the same object:

```python
x = [1, 2, 3]
y = x  # refcount is now 2

# Mutating x's memory also mutates y
# This might be intentional, or it might be a bug
```

**The Rule**: Before mutating, check `refcount == 1` (or be VERY sure you want to affect all references).

**Detection**:
```python
def refcount(addr):
    return ctypes.c_ssize_t.from_address(addr).value

def is_sole_reference(addr):
    # Note: Our own introspection adds a reference
    # So "1" when we check means "0" in normal operation
    # This is tricky - we need to account for our own reference
    return refcount(addr) <= 2  # Approximate
```

### Dictionary Keys

Dictionary keys are often shared and interned:

```python
d = {"name": "Alice"}
# The string "name" is likely interned
# Mutating it corrupts ALL dicts using "name" as a key
```

**The Rule**: Never mutate dictionary keys. If you must change a key, delete and reinsert.

### Hash Consistency

Objects used as dict keys or set members have cached hashes. If you mutate the object, the hash becomes invalid:

```python
# This would be catastrophic:
# 1. Object is in a dict with hash H
# 2. We mutate the object
# 3. New hash would be H'
# 4. Dict lookup uses H, can't find the object
# 5. Dict is now corrupted
```

**The Rule**: Never mutate objects that are dict keys or set members.

---

## SAFE: When Mutation Is Okay

### Condition 1: Sole Reference

If you're the only reference to an object, mutation affects no one else:

```python
x = [1, 2, 3]  # Created fresh, we own it
# If refcount == 1, safe to mutate
```

### Condition 2: Known Local Scope

If an object was just created and hasn't escaped:

```python
def process():
    temp = [0] * 1000  # Local, hasn't escaped
    # Safe to mutate temp's memory
    return sum(temp)
```

### Condition 3: Not Hashable / Not a Key

Mutable objects (lists, dicts, sets) can't be dict keys anyway:

```python
x = [1, 2, 3]
# Can't be a dict key, so no hash corruption risk
# Still need to check refcount
```

### Condition 4: Explicit Ownership

In shared memory scenarios, you might have explicit ownership protocols:

```python
# Process A owns slots 0-99
# Process B owns slots 100-199
# Each process can safely mutate its own slots
```

---

## Pre-Mutation Checklist

Before ANY memory write, verify:

```python
def is_safe_to_mutate(addr, type_name, value=None):
    """
    Returns (safe: bool, reason: str)
    """
    # 1. Check immortality
    if is_immortal(addr):
        return False, "Object is immortal"

    # 2. Check interning (strings)
    if type_name == 'str':
        if is_interned(addr):
            return False, "String is interned"

    # 3. Check small integer cache
    if type_name == 'int' and value is not None:
        if is_cached_int(value):
            return False, "Integer is in small int cache"

    # 4. Check refcount
    refs = refcount(addr)
    if refs > 2:  # 2 because our check adds a reference
        return False, f"Object has {refs} references (shared)"

    # 5. Check GC state
    if is_gc_running():
        return False, "GC is currently running"

    return True, "Safe to mutate"
```

---

## Type-Specific Safety Rules

### Integers

| Scenario | Safe? | Reason |
|----------|-------|--------|
| Mutate `42` in place | **NO** | Likely cached |
| Mutate `1000` with refcount=1 | Maybe | Not cached, but verify |
| Change digit count | **NO** | Would corrupt memory layout |

**Safe operation**: Mutate digits of a large, sole-reference integer without changing digit count.

### Floats

| Scenario | Safe? | Reason |
|----------|-------|--------|
| Mutate `0.0`, `1.0` | **NO** | May be cached/immortal |
| Mutate arbitrary float, refcount=1 | Yes | Simple 8-byte write |

**Safe operation**: Overwrite `ob_fval` at offset +16.

### Strings

| Scenario | Safe? | Reason |
|----------|-------|--------|
| Mutate any literal | **NO** | Interned |
| Mutate dynamically created string | Maybe | Check interned flag |
| Change string length | **NO** | Would corrupt memory |
| Change string kind | **NO** | Would corrupt memory |

**Safe operation**: Overwrite characters in a non-interned, sole-reference string of the same length.

### Lists

| Scenario | Safe? | Reason |
|----------|-------|--------|
| Replace element pointer | Yes* | Just a pointer swap |
| Change ob_size | **NO** | Must match allocated |
| Reallocate ob_item | **NO** | Complex, GC interaction |

**Safe operation**: Swap an element pointer in `ob_item` array (with proper refcount management).

### Tuples

| Scenario | Safe? | Reason |
|----------|-------|--------|
| Replace element pointer | Maybe | Tuples are "immutable" |
| Empty tuple | **NO** | Singleton |

**Note**: Mutating tuples violates Python's semantics. Only do this if you have a very specific reason.

### Dicts

| Scenario | Safe? | Reason |
|----------|-------|--------|
| Replace value pointer | Yes* | Values aren't hashed |
| Replace key pointer | **NO** | Hash table corruption |
| Add/remove entries | **NO** | Complex invariants |

**Safe operation**: Swap a value pointer in an existing entry (with proper refcount management).

---

## Refcount Management

When swapping pointers, you MUST maintain refcounts:

```python
def safe_swap_pointer(container_addr, offset, new_obj):
    """
    Swap a pointer in a container, maintaining refcounts.
    """
    # Get old pointer
    old_ptr = ctypes.c_void_p.from_address(container_addr + offset).value

    # Increment new object's refcount BEFORE the swap
    new_addr = id(new_obj)
    new_refcnt_addr = new_addr
    ctypes.c_ssize_t.from_address(new_refcnt_addr).value += 1

    # Perform the swap
    ctypes.c_void_p.from_address(container_addr + offset).value = new_addr

    # Decrement old object's refcount AFTER the swap
    if old_ptr:
        ctypes.c_ssize_t.from_address(old_ptr).value -= 1
        # Note: If this drops to 0, the object should be freed
        # But we can't trigger Python's deallocation from here
        # This is a limitation of direct memory manipulation
```

> **Warning**: Incorrect refcount management causes memory leaks or use-after-free bugs.

---

## The Nuclear Options

Some operations are so dangerous they should require explicit opt-in:

### Retype an Object

```python
def retype(addr, new_type_addr):
    """
    NUCLEAR: Change an object's type.
    This can cause segfaults, corruption, and undefined behavior.
    """
    ctypes.c_void_p.from_address(addr + 8).value = new_type_addr
```

Use case: Almost never. Maybe for debugging/research only.

### Force Refcount

```python
def force_refcount(addr, new_count):
    """
    NUCLEAR: Set an object's refcount to an arbitrary value.
    Can cause double-frees or memory leaks.
    """
    ctypes.c_ssize_t.from_address(addr).value = new_count
```

Use case: Maybe to prevent deallocation temporarily. Very dangerous.

---

## Testing Safety

Every mutation function should have tests for:

1. **Rejection of unsafe targets**:
   ```python
   def test_rejects_interned_string():
       s = "hello"  # Interned
       assert not is_safe_to_mutate(id(s), 'str')
   ```

2. **Acceptance of safe targets**:
   ```python
   def test_accepts_fresh_list():
       x = [1, 2, 3]
       assert is_safe_to_mutate(id(x), 'list')
   ```

3. **Correct behavior after mutation**:
   ```python
   def test_mutation_works():
       x = [1, 2, 3]
       mutate_list_element(x, 0, 999)
       assert x[0] == 999
   ```

4. **No corruption of shared state**:
   ```python
   def test_no_side_effects():
       a = [1, 2, 3]
       b = [1, 2, 3]  # Same content, different object
       mutate_list_element(a, 0, 999)
       assert b[0] == 1  # b unchanged
   ```

---

## Open Research Questions

1. **Can we detect dict/set membership?**
   - If an object is a key somewhere, we shouldn't mutate it
   - Python doesn't track this - can we?

2. **How do we handle free-threading (3.13+)?**
   - No GIL means concurrent access
   - Need memory barriers? Atomic operations?

3. **Can we make mutation transactional?**
   - Snapshot before mutation
   - Rollback on failure
   - Would this be useful or too slow?

4. **What's the performance cost of safety checks?**
   - Is it worth having a "fast unsafe" mode?
   - Or should safety be always-on?

---

## Summary: The Golden Rules

1. **NEVER** mutate interned strings
2. **NEVER** mutate cached integers (-5 to 256)
3. **NEVER** mutate immortal objects (None, True, False)
4. **NEVER** mutate type objects
5. **NEVER** mutate dict keys or set members
6. **NEVER** mutate during GC
7. **ALWAYS** check refcount before mutation
8. **ALWAYS** maintain refcounts when swapping pointers
9. **ALWAYS** test for rejection of unsafe targets
10. **WHEN IN DOUBT**, don't mutate

---

## API Design Implications

The scalpel API should make safe operations easy and dangerous operations hard:

```python
# Easy (safe by default)
ptr.mutate(new_value)  # Validates, raises if unsafe

# Explicit (requires acknowledgment)
ptr.mutate_unchecked(new_value)  # Skips validation

# Nuclear (requires double opt-in)
ptr.force_mutate(new_value, i_know_what_im_doing=True)
```

This design makes it hard to accidentally corrupt memory while still allowing research/debugging use cases.
