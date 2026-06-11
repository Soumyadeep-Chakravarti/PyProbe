# PyProbe API Reference

Complete API reference for all public functions and classes.

---

## Top-Level Functions

### `pin(obj) → Pointer`

Pin a live Python object for memory introspection.

```python
import pyprobe

x = {"key": "value"}
ptr = pyprobe.pin(x)
```

**Parameters**:
- `obj` (Any): The Python object to pin. The pointer holds a strong reference to prevent GC.

**Returns**: `Pointer` instance with `address`, `type_name`, and extraction methods.

**Raises**: `PyProbeError` if the object cannot be introspected.

---

### `pin_addr(addr) → Pointer`

Create a Pointer to a raw memory address.

```python
ptr = pyprobe.pin_addr(0x7f8b2c0a3d40)
```

**Parameters**:
- `addr` (int): Memory address (must be 8-byte aligned, valid Python object).

**Returns**: `Pointer` instance.

**Raises**: `PyProbeError` if the address is invalid or unreadable.

---

### `explain(obj) → str`

Generate a human-readable mutation plan for a single object.

```python
print(pyprobe.explain(3.14))
#   float  3.14
#   Address:  0x7f8b2c0a3d40
#   Size:     ~24 bytes
#
#   Verdict:  SAFE
#   Reason:   Sole reference
#
#   Function: mutate_float
#   Constraints:
#     - New value must be a finite float
#
#   Example:
#     from pyprobe import mutate_float
#     mutate_float(target, new_value)
```

**Parameters**:
- `obj` (Any): The object to analyze.

**Returns**: Formatted string with type, address, size, safety verdict, mutation function, and constraints.

---

### `audit(scope=None) → AuditReport`

Scan a scope (dict of `{name: obj}`) for mutation candidates.

```python
x = 42
y = "hello"
report = pyprobe.audit(locals())
print(f"Safe: {report.total_safe}, Unsafe: {report.total_unsafe}")
```

**Parameters**:
- `scope` (dict, optional): Dict of `{name: obj}` to scan. If `None`, scans the caller's local namespace.

**Returns**: `AuditReport` with `targets` (list of `MutationTarget`), `total_safe`, `total_unsafe`.

**`MutationTarget` fields**:
- `object_type`: Type name (e.g., `"int"`)
- `object_repr`: Repr of the object (truncated to 60 chars)
- `memory_address`: Hex address
- `size_bytes`: Estimated byte size
- `verdict`: `SafetyVerdict.SAFE` or `SafetyVerdict.UNSAFE`
- `reason`: Human-readable safety reason
- `mutation_function`: Scalpel function name (e.g., `"mutate_int"`)
- `constraints`: List of mutation constraints

---

### `audit_str(scope=None) → str`

Human-readable string version of `audit()`.

```python
print(pyprobe.audit_str(locals()))
# PyProbe Audit Report
#   Safe:   1
#   Unsafe: 2
#
#   int  42
#     Verdict:  SAFE  (Sole reference)
#     Function: mutate_int
#   ...
```

---

### `to_dict(obj) → dict`

Structured dictionary representation of mutation metadata.

```python
info = pyprobe.to_dict(3.14)
# {
#   "type": "float",
#   "repr": "3.14",
#   "address": "0x7f8b2c0a3d40",
#   "size_bytes": 24,
#   "safe_to_mutate": True,
#   "reason": "Sole reference",
#   "mutation_function": "mutate_float",
#   "constraints": ["New value must be a finite float"]
# }
```

**Returns**: Dict with keys: `type`, `repr`, `address`, `size_bytes`, `safe_to_mutate`, `reason`, `mutation_function`, `constraints`.

---

### `to_json(obj, indent=2) → str`

JSON string of mutation metadata (wrapper around `to_dict`).

```python
print(pyprobe.to_json(3.14))
```

---

### `compare(obj_a, obj_b) → dict`

Compare two objects for mutation equivalence.

```python
result = pyprobe.compare(1000, 2000)
# {
#   "type_a": "int", "type_b": "int",
#   "type_match": True, "size_match": True,
#   "safe_a": True, "safe_b": True,
#   "compatible": True,
#   "note": "Both are mutate_int targets — swap is possible"
# }
```

**Returns**: Dict with keys: `type_a`, `type_b`, `type_match`, `size_match`, `safe_a`, `safe_b`, `reason_a`, `reason_b`, `function_a`, `function_b`, `compatible`, `note`.

---

### `compare_str(obj_a, obj_b) → str`

Human-readable comparison string.

```python
print(pyprobe.compare_str(1000, 2000))
```

---

## Pointer Class

`from pyprobe import Pointer` (or via `pin()` / `pin_addr()`).

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `address` | `int` | Memory address of the pinned object |
| `type_name` | `str` | Python type name (e.g., `"int"`, `"dict"`) |
| `_target` | `Any` | Original pinned object (prevents GC) |

### Methods

#### `xray() → Any`

Extract the object's data recursively from memory.

```python
ptr = pyprobe.pin({"a": [1, 2, 3]})
data = ptr.xray()  # {'a': [1, 2, 3]}
```

#### `examine() → None`

Pretty-print full memory examination (prints to stdout).

```python
ptr = pyprobe.pin(3.14)
ptr.examine()
# Output: type, address, refcount, extracted value, etc.
```

#### `pull_data_from_address(addr) → Any`

Recursively extract data from any memory address.

```python
ptr = pyprobe.pin([1, 2, 3])
item = ptr.pull_data_from_address(ptr.address + 24)  # First list element
```

#### `mutate_float(target_slot_addr, new_val) → None`

Mutate a float object's value in-place.

```python
ptr = pyprobe.pin(3.14)
ptr.mutate_float(ptr.address, 2.71)
```

#### `mutate_int(target_addr, new_val) → None`

Mutate an int object's value in-place.

```python
ptr = pyprobe.pin(1000)
ptr.mutate_int(ptr.address, 2000)
```

#### `safe_list_swap(target_list, index, new_obj) → None`

Safely swap a list item at the given index.

```python
ptr = pyprobe.pin([1, 2, 3])
ptr.safe_list_swap([1, 2, 3], 0, 999)
```

#### `safe_dict_value_swap(target_dict, key, new_addr) → None`

Safely swap a dict value for the given key.

```python
ptr = pyprobe.pin({"a": 1})
ptr.safe_dict_value_swap({"a": 1}, "a", id(42))
```

---

## Scalpel Functions

Standalone mutation functions from `pyprobe.core.Scalpel`.

```python
from pyprobe.core.Scalpel import (
    mutate_float, mutate_int, safe_list_swap,
    safe_dict_value_swap, mutate_bytes, mutate_str
)
```

All functions accept a `safe` parameter (default `True`):
- `safe=True` — Full safety checks; raises `PyProbeSafetyError` if check fails
- `safe=False` — Skips `assert_safe()`; hard blocks (`SecurityError`, `IntegrityError`) still fire

### `mutate_float(target_float, new_value, safe=True) → None`

Mutate a float object's `ob_fval` field in-place.

```python
from pyprobe.core.Scalpel import mutate_float

x = 3.14
mutate_float(x, 2.71)  # x is now 2.71
```

**Parameters**:
- `target_float` (float): The float object to mutate
- `new_value` (float): New value (must be finite)
- `safe` (bool): If `True`, run safety checks first

**Raises**: `PyProbeSecurityError` (immortal/cached), `PyProbeSafetyError` (shared ref), `PyProbeIntegrityError` (not a float)

---

### `mutate_int(target_int, new_value, safe=True) → None`

Mutate an int object's digits in-place (cannot change digit count).

```python
from pyprobe.core.Scalpel import mutate_int

x = 1000
mutate_int(x, 2000)  # x is now 2000
```

**Constraints**:
- New value must fit in the same number of digits
- Cached integers (-5 to 256) cannot be mutated in-place
- Positive/zero/negative sign must match

**Raises**: `PyProbeSafetyError` (cached int), `PyProbeIntegrityError` (digit count mismatch), `PyProbeSecurityError` (immortal)

---

### `safe_list_swap(target_list, index, new_obj, safe=True) → None`

Swap a list element pointer at the given index.

```python
from pyprobe.core.Scalpel import safe_list_swap

x = [1, 2, 3]
safe_list_swap(x, 0, 999)  # x is now [999, 2, 3]
```

**Parameters**:
- `target_list` (list): The list to modify
- `index` (int): Index of the element to swap
- `new_obj` (Any): New object to place at that index

**Raises**: `IndexError` (out of bounds), `PyProbeSafetyError` (shared list), `PyProbeIntegrityError` (not a list)

---

### `safe_dict_value_swap(target_dict, key, new_value, safe=True) → None`

Swap a dict value for the given key.

```python
from pyprobe.core.Scalpel import safe_dict_value_swap

x = {"a": 1, "b": 2}
safe_dict_value_swap(x, "a", 99)  # x is now {"a": 99, "b": 2}
```

**Parameters**:
- `target_dict` (dict): The dict to modify
- `key` (Any): Key whose value to swap
- `new_value` (Any): New value

**Raises**: `KeyError` (key not found), `PyProbeSafetyError` (shared dict), `PyProbeIntegrityError` (value pointer scan failure)

---

### `mutate_bytes(target_bytes, new_bytes, safe=True) → None`

Mutate a bytes object's data in-place.

```python
from pyprobe.core.Scalpel import mutate_bytes

x = b"hello"
mutate_bytes(x, b"world")  # x is now b"world"
```

**Constraints**: New bytes must be exactly the same length.

**Raises**: `PyProbeSecurityError` (interned bytes), `ValueError` (length mismatch), `PyProbeIntegrityError` (not bytes)

---

### `mutate_str(target_str, new_str, safe=True) → None`

Mutate a string object's data in-place.

```python
from pyprobe.core.Scalpel import mutate_str

x = "hello"
mutate_str(x, "world")  # x is now "world"
```

**Constraints**: New string must be exactly the same length, Compact ASCII encoding only.

**Raises**: `PyProbeSecurityError` (interned string), `ValueError` (length/encoding mismatch), `PyProbeIntegrityError` (not a string)

---

## Exception Hierarchy

```python
from pyprobe import (
    PyProbeError,
    PyProbeSecurityError,
    PyProbeIntegrityError,
    PyProbeSafetyError,
    PyProbeWarning,
)
```

| Exception | Severity | Bypassable? | Example |
|-----------|----------|-------------|---------|
| `PyProbeError` | Base class | — | — |
| `PyProbeSecurityError` | HARD block | No | Interned string, live bytecode |
| `PyProbeIntegrityError` | HARD block | No | Length mismatch, dict scan failure |
| `PyProbeSafetyError` | SOFT block | Yes (`safe=False`) | Shared ref, cached int |
| `PyProbeWarning` | Warning | N/A | Non-fatal conditions |

---

## Environment Variables

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `PYPROBE_COLOR` | `auto`, `always`, `never` | `auto` | ANSI color output control |
| `PYPROBE_COLOR_MODE` | `normal`, `colorblind` | `normal` | Colorblind-safe palette |

`auto` mode enables colors only when stdout is a TTY (respects `NO_COLOR`).
