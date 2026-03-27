# CPython Memory Internals Reference

This document is the knowledge base for CPython's internal memory layouts. It serves as a reference for implementing extractors and (eventually) mutators.

> **Target Versions**: CPython 3.12, 3.13, 3.14+ (64-bit only)

---

## Table of Contents

1. [Foundational Concepts](#foundational-concepts)
2. [PyObject_HEAD](#pyobject_head)
3. [Integer (PyLongObject)](#integer-pylongobject)
4. [Float (PyFloatObject)](#float-pyfloatobject)
5. [String (PyUnicodeObject)](#string-pyunicodeobject)
6. [Bytes (PyBytesObject)](#bytes-pybytesobject)
7. [List (PyListObject)](#list-pylistobject)
8. [Tuple (PyTupleObject)](#tuple-pytupleobject)
9. [Dictionary (PyDictObject)](#dictionary-pydictobject)
10. [Set (PySetObject)](#set-pysetobject)
11. [NoneType and Singletons](#nonetype-and-singletons)
12. [Version-Specific Changes](#version-specific-changes)
13. [Quick Reference Table](#quick-reference-table)

---

## Foundational Concepts

### Memory Alignment

All Python objects are **8-byte aligned** on 64-bit systems. This means:
- Every object address ends in `0x0` or `0x8`
- Address & 0x7 == 0 (always)

This is a useful validation check.

### Object Identity

In CPython, `id(obj)` returns the **memory address** of the object. This is the starting point for all introspection.

```python
x = [1, 2, 3]
addr = id(x)  # e.g., 0x7f1234567890
```

### Reference Counting

CPython uses reference counting for memory management. Every object has a reference count (`ob_refcnt`) at offset 0.

```python
import sys
sys.getrefcount(x)  # Returns refcount + 1 (the call itself adds a reference)
```

### The GIL

The Global Interpreter Lock (GIL) protects CPython's memory management. In single-threaded code, we don't need to worry about concurrent modification during introspection.

> **Note**: Python 3.13+ introduces free-threading (no-GIL) mode. This changes safety assumptions significantly.

---

## PyObject_HEAD

**Every** Python object starts with this header:

```
Offset  Field         Size   Description
──────────────────────────────────────────────
+0      ob_refcnt     8      Reference count
+8      ob_type       8      Pointer to type object
──────────────────────────────────────────────
Total: 16 bytes
```

**ctypes definition**:
```python
class PyObjectHeader(ctypes.Structure):
    _fields_ = [
        ("ob_refcnt", ctypes.c_ssize_t),   # Py_ssize_t
        ("ob_type_ptr", ctypes.c_void_p),  # PyTypeObject*
    ]
```

### PyVarObject_HEAD

Variable-size objects (list, tuple, etc.) extend the header:

```
Offset  Field         Size   Description
──────────────────────────────────────────────
+0      ob_refcnt     8      Reference count
+8      ob_type       8      Pointer to type object
+16     ob_size       8      Number of items
──────────────────────────────────────────────
Total: 24 bytes
```

> **Important**: Not all "variable" objects use `PyVarObject`. Dicts have their own layout.

---

## Integer (PyLongObject)

CPython integers are arbitrary-precision. They're stored as arrays of 30-bit "digits".

### Memory Layout (3.12+)

```
Offset  Field         Size   Description
──────────────────────────────────────────────
+0      ob_refcnt     8      Reference count
+8      ob_type       8      Pointer to int type
+16     lv_tag        8      Size and sign encoded
+24     ob_digit[0]   4      First digit (30-bit)
+28     ob_digit[1]   4      Second digit (if needed)
...
──────────────────────────────────────────────
```

### lv_tag Encoding (3.12+)

The `lv_tag` field encodes both size and sign:

```python
tag = ctypes.c_size_t.from_address(addr + 16).value
size = tag >> 3          # Number of digits (absolute value)
negative = (tag >> 1) & 1  # 1 if negative, 0 if positive
```

### Digit Representation

- Each digit is 30 bits (not 32, to prevent overflow during multiplication)
- Base is 2^30 = 1,073,741,824
- Stored in **little-endian** order (least significant digit first)

**Reconstruction**:
```python
result = 0
for i in range(size):
    digit = ctypes.c_uint32.from_address(addr + 24 + i*4).value
    result += digit * (2 ** (30 * i))
if negative:
    result = -result
```

### Small Integer Cache

CPython caches integers from -5 to 256. These are **singletons**:

```python
a = 256
b = 256
assert a is b  # True - same object!

a = 257
b = 257
assert a is b  # False - different objects
```

> **Warning**: Mutating a cached integer would corrupt ALL references to that value!

---

## Float (PyFloatObject)

The simplest object after the header.

### Memory Layout

```
Offset  Field         Size   Description
──────────────────────────────────────────────
+0      ob_refcnt     8      Reference count
+8      ob_type       8      Pointer to float type
+16     ob_fval       8      IEEE 754 double
──────────────────────────────────────────────
Total: 24 bytes
```

**Extraction**:
```python
value = ctypes.c_double.from_address(addr + 16).value
```

---

## String (PyUnicodeObject)

Strings are complex. CPython uses different representations based on content.

### Memory Layout (Compact ASCII)

Most common case - ASCII-only strings:

```
Offset  Field         Size   Description
──────────────────────────────────────────────
+0      ob_refcnt     8      Reference count
+8      ob_type       8      Pointer to str type
+16     length        8      Character count
+24     hash          8      Cached hash (-1 if not computed)
+32     [bitfields]   4      State flags (see below)
+36     [padding]     4      Alignment
+40     data[0]       1      First character (inline)
...
──────────────────────────────────────────────
```

### Bitfield Layout (offset +32)

```
Bits    Field      Description
────────────────────────────────────────
0-1     interned   Interning state (0-3)
2-4     kind       Encoding: 1=1byte, 2=2byte, 4=4byte
5       compact    1=data is inline after header
6       ascii      1=all characters < 128
7       ready      1=fully initialized (always 1 in 3.12+)
8-31    [padding]  Unused
```

### String Kinds

| Kind | Char Size | Encoding | When Used |
|------|-----------|----------|-----------|
| 1 | 1 byte | ASCII or Latin-1 | chars <= U+00FF |
| 2 | 2 bytes | UCS-2 | chars <= U+FFFF |
| 4 | 4 bytes | UCS-4/UTF-32 | any Unicode |

### Non-ASCII Compact Strings

For non-ASCII content, there's extra header space:

```
Offset  Field         Size   Description
──────────────────────────────────────────────
+0      ob_refcnt     8      Reference count
+8      ob_type       8      Pointer to str type
+16     length        8      Character count
+24     hash          8      Cached hash
+32     [bitfields]   4      State flags
+36     [padding]     4      Alignment
+40     utf8_length   8      Cached UTF-8 length
+48     utf8_ptr      8      Cached UTF-8 pointer
+56     data[0]       var    First character (inline)
...
──────────────────────────────────────────────
```

### String Interning

Some strings are "interned" (shared globally):
- String literals in source code
- Attribute names
- Dictionary keys (sometimes)

```python
a = "hello"
b = "hello"
assert a is b  # True - interned!
```

> **Warning**: Mutating an interned string corrupts ALL references!

---

## Bytes (PyBytesObject)

Immutable byte sequences with inline storage.

### Memory Layout

```
Offset  Field         Size   Description
──────────────────────────────────────────────
+0      ob_refcnt     8      Reference count
+8      ob_type       8      Pointer to bytes type
+16     ob_size       8      Byte count
+24     ob_shash      8      Cached hash (-1 if not computed)
+32     ob_sval[0]    1      First byte (inline)
...
──────────────────────────────────────────────
```

**Extraction**:
```python
size = ctypes.c_ssize_t.from_address(addr + 16).value
data = ctypes.string_at(addr + 32, size)
```

---

## List (PyListObject)

Dynamic arrays with **indirect storage** - the items are stored in a separate allocation.

### Memory Layout

```
Offset  Field         Size   Description
──────────────────────────────────────────────
+0      ob_refcnt     8      Reference count
+8      ob_type       8      Pointer to list type
+16     ob_size       8      Current item count
+24     ob_item       8      POINTER to PyObject* array
+32     allocated     8      Allocated capacity
──────────────────────────────────────────────
Total: 40 bytes (header only)
```

### Item Storage

`ob_item` points to a separately allocated array:

```
ob_item ──► ┌──────────────┐
            │ PyObject* 0  │  8 bytes
            │ PyObject* 1  │  8 bytes
            │ PyObject* 2  │  8 bytes
            │ ...          │
            └──────────────┘
```

**Extraction**:
```python
size = ctypes.c_ssize_t.from_address(addr + 16).value
items_ptr = ctypes.c_void_p.from_address(addr + 24).value
items = ctypes.cast(items_ptr, ctypes.POINTER(ctypes.c_void_p))
for i in range(size):
    element_addr = items[i]
    # ... extract element
```

### Overallocation

Lists overallocate to make `append()` amortized O(1):

```python
allocated >= ob_size  # Always
# Growth pattern: 0, 4, 8, 16, 24, 32, 40, 52, 64, ...
```

---

## Tuple (PyTupleObject)

Fixed-size sequences with **inline storage** - items stored directly after header.

### Memory Layout (3.12+)

```
Offset  Field         Size   Description
──────────────────────────────────────────────
+0      ob_refcnt     8      Reference count
+8      ob_type       8      Pointer to tuple type
+16     ob_size       8      Item count
+24     hash_cached   8      Cached hash (NEW in 3.12)
+32     ob_item[0]    8      First item (inline)
+40     ob_item[1]    8      Second item
...
──────────────────────────────────────────────
```

> **Version Note**: Before 3.12, items started at +24 (no hash_cached field).

**Extraction**:
```python
size = ctypes.c_ssize_t.from_address(addr + 16).value
items = ctypes.cast(addr + 32, ctypes.POINTER(ctypes.c_void_p))
for i in range(size):
    element_addr = items[i]
    # ... extract element
```

### Empty Tuple Singleton

The empty tuple `()` is a singleton:

```python
a = ()
b = ()
assert a is b  # True
```

---

## Dictionary (PyDictObject)

The most complex built-in type. Uses a split-table design.

### Memory Layout

```
Offset  Field           Size   Description
──────────────────────────────────────────────
+0      ob_refcnt       8      Reference count
+8      ob_type         8      Pointer to dict type
+16     ma_used         8      Number of active entries
+24     ma_version_tag  8      Version (for optimization)
+32     ma_keys         8      POINTER to DictKeysObject
+40     ma_values       8      POINTER to values (split) or NULL
──────────────────────────────────────────────
Total: 48 bytes
```

> **Note**: Dict is NOT a PyVarObject - no ob_size in header.

### DictKeysObject Layout (3.14)

```
Offset  Field                Size   Description
──────────────────────────────────────────────
+0      dk_refcnt            8      Keys can be shared
+8      dk_log2_size         1      Log2 of hash table size
+9      dk_log2_index_bytes  1      Log2 of index array total size
+10     dk_kind              1      0=GENERAL, 1=UNICODE
+11     dk_version_header    1      Version info
+12     dk_version           4      Dict version
+16     dk_usable            8      Slots before resize needed
+24     dk_nentries          8      Total entries (incl. deleted)
+32     [indices]            var    Hash table (variable size)
+32+N   [entries]            var    Dense entry array
──────────────────────────────────────────────
```

### Index Array

The indices array maps hash slots to entry positions:

- Size: `1 << dk_log2_index_bytes` bytes
- Each index is 1, 2, or 4 bytes depending on dict size
- Special values: -1 (empty), -2 (deleted/dummy)

### Entry Formats

**Unicode Keys (dk_kind=1)**:
```
Offset  Field     Size   Description
+0      me_key    8      Pointer to key (must be str)
+8      me_value  8      Pointer to value
────────────────────────
Stride: 16 bytes
```

**General Keys (dk_kind=0)**:
```
Offset  Field     Size   Description
+0      me_hash   8      Cached hash
+8      me_key    8      Pointer to key
+16     me_value  8      Pointer to value
────────────────────────
Stride: 24 bytes
```

### Tombstones (Dummy Entries)

When a key is deleted, it leaves a "tombstone" - a special `<dummy>` singleton that marks the slot as deleted but not empty (to preserve probe sequences).

```python
_DUMMY_PTR = None  # Discovered lazily

def is_dummy(key_ptr):
    return key_ptr == _DUMMY_PTR
```

---

## Set (PySetObject)

Sets use a simpler hash table than dicts.

### Memory Layout

```
Offset  Field           Size   Description
──────────────────────────────────────────────
+0      ob_refcnt       8      Reference count
+8      ob_type         8      Pointer to set type
+16     fill            8      Active + dummy count
+24     used            8      Active entries only
+32     mask            8      Hash table size - 1
+40     table           8      POINTER to setentry array
+48     hash            8      Cached hash (frozenset only)
+56     finger          8      Search finger optimization
+64     smalltable[0]   128    Inline table for small sets
──────────────────────────────────────────────
```

### Set Entry

```
Offset  Field     Size   Description
+0      key       8      Pointer to key (or NULL/dummy)
+8      hash      8      Cached hash
────────────────────────
Stride: 16 bytes
```

### Small Set Optimization

Sets with <= 8 elements use the inline `smalltable` at offset +64 instead of a separate allocation.

---

## NoneType and Singletons

### None

`None` is a singleton with no payload:

```python
assert id(None) == id(None)  # Always true
```

Layout is just `PyObject_HEAD` (16 bytes).

### True/False

Boolean singletons:

```python
assert True is True
assert False is False
```

### Ellipsis

`...` (Ellipsis) is also a singleton.

---

## Version-Specific Changes

### Python 3.12

- **Integers**: New `lv_tag` encoding (was `ob_size` + sign bit before)
- **Tuples**: Added `hash_cached` field at +24
- **Immortal objects**: PEP 683 - some objects have special refcount

### Python 3.13

- **Free-threading**: Optional no-GIL mode changes memory safety assumptions
- **Dict**: Minor internal optimizations

### Python 3.14

- **Dict**: `dk_log2_index_bytes` at offset +9 (was computed differently before)
- Various internal optimizations

---

## Quick Reference Table

| Type | Header Size | Data Offset | Storage |
|------|-------------|-------------|---------|
| int | 16 | +16 (lv_tag), +24 (digits) | Inline |
| float | 16 | +16 | Inline |
| str (ASCII) | 16 | +40 | Inline |
| str (non-ASCII) | 16 | +56 | Inline |
| bytes | 16 | +32 | Inline |
| list | 16 | +24 (pointer) | Indirect |
| tuple | 16 | +32 | Inline |
| dict | 16 | +32 (ma_keys pointer) | Indirect |
| set | 16 | +40 (table pointer) | Indirect* |

\* Sets use inline storage for <= 8 elements.

---

## Magic Numbers Reference

```python
# Header sizes
HEADER_SIZE = 16          # PyObject_HEAD
VAR_HEADER_SIZE = 24      # PyVarObject_HEAD

# Validation
MIN_VALID_ADDR = 0x1000   # Below this is typically unmapped
ALIGNMENT_MASK = 0x7      # addr & 0x7 must equal 0

# Integer
INT_TAG_OFFSET = 16
INT_DIGITS_OFFSET = 24
INT_DIGIT_BITS = 30
INT_DIGIT_BASE = 1 << 30

# String
STR_LENGTH_OFFSET = 16
STR_HASH_OFFSET = 24
STR_STATE_OFFSET = 32
STR_ASCII_DATA_OFFSET = 40
STR_NONASCII_DATA_OFFSET = 56

# List
LIST_SIZE_OFFSET = 16
LIST_ITEMS_OFFSET = 24
LIST_ALLOCATED_OFFSET = 32

# Tuple (3.12+)
TUPLE_SIZE_OFFSET = 16
TUPLE_HASH_OFFSET = 24
TUPLE_ITEMS_OFFSET = 32

# Dict
DICT_USED_OFFSET = 16
DICT_KEYS_OFFSET = 32
DICT_VALUES_OFFSET = 40
DICTKEYS_HEADER_SIZE = 32

# Set
SET_FILL_OFFSET = 16
SET_USED_OFFSET = 24
SET_MASK_OFFSET = 32
SET_TABLE_OFFSET = 40
```

---

## Further Reading

- [CPython Source Code](https://github.com/python/cpython)
- [Python Developer's Guide](https://devguide.python.org/)
- [PEP 683 - Immortal Objects](https://peps.python.org/pep-0683/)
- [PEP 659 - Specializing Adaptive Interpreter](https://peps.python.org/pep-0659/)
