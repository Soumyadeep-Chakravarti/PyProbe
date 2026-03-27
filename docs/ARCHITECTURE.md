# PyProbe Architecture

This document describes the system design, code organization, and key design patterns used in PyProbe.

---

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Code                               │
│                   pyprobe.pin(obj) / pin_addr(addr)             │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Public API Layer                           │
│                    src/pyprobe/__init__.py                      │
│                                                                 │
│   pin(obj) ──────► Pointer(target=obj)                          │
│   pin_addr(addr) ► Pointer(address=addr)                        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Engine Layer                              │
│               src/pyprobe/core/pointer/engine.py                │
│                                                                 │
│   Pointer class:                                                │
│   ├── __init__()      → Read header, determine type             │
│   ├── xray()          → Full memory examination                 │
│   ├── examine()       → Pretty-printed inspection               │
│   ├── pull_data_from_address() → Recursive extraction           │
│   └── _extract_*()    → Type-specific extractors                │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Raw Structures Layer                         │
│                       src/pyprobe/raw/                          │
│                                                                 │
│   headers/                    │   lenses/                       │
│   ├── py_object.py           │   ├── int_lens.py               │
│   ├── py_type.py             │   ├── float_lens.py             │
│   ├── py_long.py             │   ├── str_lens.py               │
│   ├── py_float.py            │   ├── list_lens.py              │
│   ├── py_unicode.py          │   ├── tuple_lens.py             │
│   ├── py_list.py             │   ├── dict_lens.py              │
│   ├── py_tuple.py            │   ├── set_lens.py               │
│   ├── py_dict.py             │   └── bytes_lens.py             │
│   └── py_collections.py      │                                  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      CPython Memory                             │
│              (Actual object bytes in process memory)            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
PyProbe/
├── src/
│   └── pyprobe/
│       ├── __init__.py              # Public API: pin(), pin_addr()
│       ├── core/
│       │   ├── __init__.py
│       │   ├── common.py            # (Reserved for shared utilities)
│       │   └── pointer/
│       │       ├── __init__.py
│       │       └── engine.py        # The Pointer class (626 lines)
│       └── raw/
│           ├── headers/             # Full CPython struct mirrors
│           │   ├── __init__.py
│           │   ├── py_object.py     # PyObject_HEAD
│           │   ├── py_type.py       # PyTypeObject (partial)
│           │   ├── py_long.py       # PyLongObject
│           │   ├── py_float.py      # PyFloatObject
│           │   ├── py_unicode.py    # PyASCIIObject, PyCompactUnicodeObject
│           │   ├── py_list.py       # PyListObject
│           │   ├── py_tuple.py      # PyTupleObject
│           │   ├── py_dict.py       # PyDictObject, DictKeysObject
│           │   └── py_collections.py # PyBytesObject, PySetObject
│           └── lenses/              # Body-only "surgical" views
│               ├── __init__.py
│               ├── int_lens.py
│               ├── float_lens.py
│               ├── str_lens.py
│               ├── list_lens.py
│               ├── tuple_lens.py
│               ├── dict_lens.py
│               ├── set_lens.py
│               └── bytes_lens.py
├── tools/
│   ├── explorer_repl.py             # Interactive memory REPL
│   └── leak_tracker.py              # Reference count tracker
├── tests/
│   ├── run_all.py                   # Test runner
│   ├── test_primitives.py           # Scalar types
│   ├── test_collections.py          # Container types
│   ├── test_graphs.py               # Cycles and recursion
│   ├── test_safety.py               # Edge cases and corruption
│   └── ...                          # Discovery/debug scripts
├── examples/
│   └── complex_graph.py             # Usage demonstration
├── docs/
│   ├── INDEX.md                     # This documentation
│   └── ...
├── main.py                          # Demo script
├── pyproject.toml                   # Project configuration
└── README.md                        # Project overview
```

---

## Key Design Patterns

### 1. Headers vs. Lenses (Dual-Layer Abstraction)

This is the most important design decision in PyProbe.

**Problem**: CPython objects all start with a common header (`PyObject_HEAD`), followed by type-specific data. When we want to read the type-specific data, we need to skip the header.

**Solution**: Two sets of structures:

| Layer | Purpose | Starts At |
|-------|---------|-----------|
| **Headers** | Full struct including `PyObject_HEAD` | Address + 0 |
| **Lenses** | Body-only, skips header | Address + 16 |

**Example**:
```python
# Header approach - full structure
from pyprobe.raw.headers.py_float import PyFloatObject
obj = PyFloatObject.from_address(addr)
value = obj.ob_fval  # Works, but includes refcnt, type ptr

# Lens approach - surgical view
from pyprobe.raw.lenses.float_lens import FloatLens
lens = FloatLens.from_address(addr + 16)  # Skip header
value = lens.ob_fval  # Just the payload
```

**Why both?**
- Headers: Needed to read `ob_refcnt` and `ob_type` for type identification
- Lenses: Cleaner for extracting payload data

### 2. Type Dispatcher Pattern

The `Pointer` class uses a dispatcher dictionary to route extraction to type-specific methods:

```python
class Pointer:
    def __init__(self, ...):
        self._extractors = {
            'int': self._extract_int,
            'float': self._extract_float,
            'str': self._extract_string,
            'list': self._extract_list,
            'tuple': self._extract_tuple,
            'dict': self._extract_dict,
            'bytes': self._extract_bytes,
            'set': self._extract_set,
            'frozenset': self._extract_set,
        }

    def pull_data_from_address(self, addr, ...):
        type_name = self._get_type_name(addr)
        extractor = self._extractors.get(type_name)
        if extractor:
            return extractor(addr, ...)
        return f"<{type_name} @ {hex(addr)}>"
```

**Why?**
- Easy to extend with new types
- Clear separation of extraction logic
- Fallback for unknown types

### 3. Singleton Discovery (Tombstone Detection)

Dictionaries and sets use a special `<dummy>` singleton to mark deleted entries. We need to detect and skip these.

```python
_DUMMY_PTR: Optional[int] = None

def _get_dummy_ptr() -> Optional[int]:
    """Lazily discover the <dummy> singleton address."""
    global _DUMMY_PTR
    if _DUMMY_PTR is None:
        # Create a tombstone by deleting from a dict
        d = {0: 0}
        del d[0]
        # ... extract the dummy pointer from the dict's internals
    return _DUMMY_PTR
```

**Why lazy?**
- We don't always need it
- Discovery requires creating a temporary dict

### 4. Cycle Detection via Visited Set

Recursive extraction tracks visited container addresses:

```python
def pull_data_from_address(self, addr, visited=None, depth=0):
    if visited is None:
        visited = set()

    if addr in visited:
        return f"<Cycle @ {hex(addr)}>"

    if type_name in ['list', 'tuple', 'dict']:
        visited.add(addr)

    # ... recurse into children
```

**Note**: Only containers are tracked. Primitives may be interned (shared), but visiting them multiple times is harmless.

---

## Core Components

### Pointer Class (`engine.py`)

The central class, ~626 lines. Key methods:

| Method | Purpose |
|--------|---------|
| `__init__(target)` | Pin an object, read header, determine type |
| `xray()` | Return extracted data as Python value |
| `examine()` | Pretty-print full memory examination |
| `pull_data_from_address(addr)` | Recursively extract data from any address |
| `_extract_int(addr)` | Integer extraction (handles multi-precision) |
| `_extract_float(addr)` | Float extraction (IEEE 754) |
| `_extract_string(addr)` | String extraction (multi-encoding) |
| `_extract_list(addr, visited, depth)` | List extraction (indirect storage) |
| `_extract_tuple(addr, visited, depth)` | Tuple extraction (inline storage) |
| `_extract_dict(addr, visited, depth)` | Dict extraction (most complex) |
| `_extract_set(addr, visited, depth)` | Set/frozenset extraction |
| `_extract_bytes(addr)` | Bytes extraction |
| `_get_type_info(addr)` | Read header, validate, get type name |
| `_normalize_address(addr)` | Handle ctypes.c_void_p vs int |

### Constants

```python
HEADER_SIZE = 16      # PyObject_HEAD: refcnt(8) + type_ptr(8)
VAR_HEADER_SIZE = 24  # PyVarObject_HEAD: adds ob_size(8)
```

### Architecture Guard

```python
if ctypes.sizeof(ctypes.c_void_p) != 8:
    raise RuntimeError("PyProbe only supports 64-bit CPython")
```

---

## Data Flow: How Extraction Works

```
User calls: pyprobe.pin(my_dict).xray()
                    │
                    ▼
            Pointer.__init__()
            ├── Store reference to prevent GC
            ├── Get address via id()
            ├── Read PyObjectHeader at address
            ├── Read type name from PyTypeObject
            └── Attach appropriate lens
                    │
                    ▼
            Pointer.xray()
            └── calls pull_data_from_address(self.address)
                    │
                    ▼
            pull_data_from_address()
            ├── Validate address (alignment, range)
            ├── Check for cycles
            ├── Check depth limit
            ├── Get type name
            ├── Dispatch to _extract_dict()
            │           │
            │           ▼
            │   _extract_dict()
            │   ├── Read ma_keys pointer
            │   ├── Calculate entry offsets
            │   ├── For each entry:
            │   │   ├── Skip if NULL or dummy
            │   │   ├── Recursively extract key
            │   │   └── Recursively extract value
            │   └── Return dict
            │
            └── Return final Python dict
```

---

## Future Architecture (Phase 2: Scalpel)

The scalpel phase will add write capabilities. Proposed structure:

```
src/pyprobe/
├── core/
│   ├── pointer/
│   │   ├── engine.py       # Existing read functionality
│   │   └── mutator.py      # NEW: Write functionality
│   └── safety/
│       ├── guards.py       # NEW: Pre-mutation safety checks
│       └── invariants.py   # NEW: Invariant verification
```

New methods on `Pointer`:
- `poke(offset, value)` - Raw memory write
- `mutate_int(new_value)` - Type-aware integer mutation
- `mutate_list_element(index, new_ptr)` - List surgery
- `is_safe_to_mutate()` - Safety check

See [SAFETY_MODEL.md](./SAFETY_MODEL.md) for the safety analysis guiding this design.

---

## Testing Strategy

| Test File | Coverage |
|-----------|----------|
| `test_primitives.py` | int, float, str, bytes |
| `test_collections.py` | list, tuple, dict, set |
| `test_graphs.py` | Cycles, deep nesting |
| `test_safety.py` | NULL, corruption, invalid addresses |

Run all tests:
```bash
python tests/run_all.py
# or
python -m pytest tests/
```

---

## Performance Considerations

1. **Type name caching**: `_TYPE_NAME_CACHE` avoids repeated type lookups
2. **Lazy dummy discovery**: `_get_dummy_ptr()` only runs when needed
3. **Direct memory access**: No Python API overhead for reading
4. **Minimal object creation**: Lenses are applied in-place, not copied

---

## Adding Support for New Types

To add extraction for a new type (e.g., `deque`):

1. **Create a lens** in `src/pyprobe/raw/lenses/deque_lens.py`:
   ```python
   class DequeLens(ctypes.Structure):
       _fields_ = [
           # ... type-specific fields after header
       ]
   ```

2. **Add an extractor** in `engine.py`:
   ```python
   def _extract_deque(self, addr, visited, depth):
       # ... extraction logic
   ```

3. **Register in dispatcher**:
   ```python
   self._extractors['collections.deque'] = self._extract_deque
   ```

4. **Add tests** in `tests/test_collections.py`

---

## Dependencies

**Runtime**: None (pure stdlib, uses `ctypes`)

**Development**: 
- Python 3.12+ (required)
- pytest (optional, for testing)
