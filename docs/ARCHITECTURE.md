# PyProbe Architecture

This document describes the system design, code organization, and key design patterns used in PyProbe.

---

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Code                               │
│      pyprobe.pin(obj) / pin_addr(addr) / explain(obj) / ...    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Public API Layer                           │
│                    src/pyprobe/__init__.py                      │
│                                                                 │
│   pin(obj) ──────► Pointer(target=obj)                          │
│   pin_addr(addr) ► Pointer(address=addr)                        │
│   explain(obj) ──► UX inspection report                        │
│   audit(scope) ──► Safety audit report                          │
│   to_json(obj) ──► Structured JSON output                      │
│   compare(a,b) ──► Side-by-side comparison                      │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Engine Layer                               │
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
│                  Mutation Layer (Scalpel)                        │
│              src/pyprobe/core/Scalpel.py                        │
│                                                                 │
│   mutate_float()    - In-place float mutation                   │
│   mutate_int()      - In-place int mutation                     │
│   safe_list_swap()  - List item swap                            │
│   safe_dict_value_swap() - Dict value swap                      │
│   mutate_bytes()    - In-place bytes mutation                   │
│   mutate_str()      - In-place string mutation                  │
│                                                                 │
│   All functions: gc_suspend/resume, assert_safe, safe param     │
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
│       ├── __init__.py              # Public API: pin(), pin_addr(), exceptions, UX
│       ├── core/
│       │   ├── __init__.py          # Exports Pointer + exceptions
│       │   ├── common.py            # PyProbeError hierarchy (5 classes)
│       │   ├── Scalpel.py           # Mutation functions + safety checks
│       │   ├── offset_discovery.py  # Dynamic offset discovery
│       │   ├── ux.py                # explain(), audit(), to_json(), compare()
│       │   └── pointer/
│       │       ├── __init__.py
│       │       └── engine.py        # The Pointer class
│       └── raw/
│           ├── headers/             # Full CPython struct mirrors
│           └── lenses/              # Body-only "surgical" views
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
    # Class-level extractor table (recommended for v2.0)
    _extractors: Dict[str, ExtractorFunc] = {
        'int': Pointer._extract_int,
        'float': Pointer._extract_float,
        'str': Pointer._extract_string,
        'list': Pointer._extract_list,
        'tuple': Pointer._extract_tuple,
        'dict': Pointer._extract_dict,
        'bytes': Pointer._extract_bytes,
        'set': Pointer._extract_set,
        'frozenset': Pointer._extract_set,
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

**Binding semantics**: All extractors are bound methods that only depend on `self`. Moving to class level is semantically equivalent — no closures or captures from `__init__` are used.

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

### Dynamic Offset Discovery

Instead of hardcoding memory offsets, PyProbe now dynamically discovers them at runtime:

```python
# In src/pyprobe/core/offset_discovery.py
TUPLE_ITEMS_OFFSET = _discover_tuple_items_offset()   # e.g., 32
LIST_ITEMS_OFFSET = _discover_list_items_offset()     # e.g., 24
DICT_MA_KEYS_OFFSET = _discover_dict_entry_layout()["ma_keys_offset"]  # e.g., 16
```

This approach eliminates version-specific checks and makes PyProbe more robust across different CPython versions.

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

## Current Architecture (Phase 2: Scalpel - Integrated)

The scalpel phase has been integrated into the Pointer class. Mutation capabilities are now available directly on Pointer instances.

### Exception Hierarchy

All custom exceptions are defined in `src/pyprobe/core/common.py`:

```python
PyProbeError                  # Base class for all PyProbe exceptions
├── PyProbeFatalError         # HARD block (no bypass) — unrecoverable CPython state
│   └── "Unrecoverable condition: ..."
├── PyProbeSecurityError      # HARD block (no bypass) — immutable/protected objects
│   └── "Cannot mutate immutable/protected object: ..."
├── PyProbeIntegrityError     # HARD block (no bypass) — would corrupt memory/state
│   └── "Length mismatch, dict scan failure, ..."
├── PyProbeSafetyError        # SOFT block (bypassable with safe=False)
│   └── "Assertion failed: ..."
├── PyProbeWarning            # Standalone (not subclass of PyProbeError)
│   └── "Warning message"
```

**Three severity tiers**:
- **SecurityError** (HARD): Always raises, no way to bypass. Used for interned strings, live bytecode.
- **IntegrityError** (HARD): Always raises. Used for length mismatches, dict scan failures.
- **SafetyError** (SOFT): Blocked by default. Skippable via `safe=False` on mutation functions.
- **Warning** standalone: Used for non-fatal warnings, not part of `PyProbeError` tree.

Standard exceptions (`IndexError`, `KeyError`, `MemoryError`, `ValueError`) are kept where semantically correct.

### Mutation Methods on Pointer

The Pointer class now includes the following mutation methods that delegate to Scalpel functions:

- `mutate_float(new_value)` - Safely mutate a float object's value in-place
- `mutate_int(new_value)` - Safely mutate an int object's value in-place (with small int cache protection)
- `safe_list_swap(index, new_obj)` - Safely swap a list item at the given index
- `safe_dict_value_swap(key, new_value)` - Safely swap a dict value for the given key
- `mutate_bytes(new_value)` - Safely mutate bytes object in-place
- `mutate_str(new_value)` - Safely mutate string object in-place

All mutation methods accept a `safe` parameter (default `True`):
- `safe=True` — Full safety checks via `assert_safe()`; `PyProbeSafetyError` raised if check fails
- `safe=False` — Skips `assert_safe()` entirely; `PyProbeSecurityError` and `PyProbeIntegrityError` still fire

### Safety Checks

Each mutation function performs three tiers of checks:
1. **Hard blocks** (always fire, `safe=False` cannot bypass):
   - `PyProbeSecurityError`: immutable/protected objects (interned strings, live bytecode)
   - `PyProbeIntegrityError`: would corrupt memory/state (length mismatch, dict scan failure)
2. **Soft blocks** (bypassable with `safe=False`):
   - `PyProbeSafetyError`: shared references, cached small ints, etc.
3. **No check needed**:
   - `PyProbeWarning`: standalone warnings for non-fatal conditions

See [SAFETY_MODEL.md](./SAFETY_MODEL.md) for the complete safety analysis.

### Internal Structure

The mutation functionality leverages:
- `src/pyprobe/core/Scalpel.py` - Core mutation functions with safety checks
- `src/pyprobe/core/offset_discovery.py` - Dynamic offset discovery for internal data structures
- Existing Pointer class infrastructure for type checking and address validation

---

## UX Module

`src/pyprobe/core/ux.py` provides high-level inspection and comparison utilities:

| Function | Purpose |
|----------|---------|
| `explain(obj)` | Pretty-print memory inspection report (ANSI color support) |
| `audit(scope)` | Audit scope objects for safety/blocking conditions |
| `audit_str(scope)` | Audit as string (no ANSI) |
| `to_dict(obj)` | Structured memory inspection as Python dict |
| `to_json(obj)` | Structured memory inspection as JSON string |
| `compare(a, b)` | Side-by-side memory comparison with diff highlights |
| `compare_str(a, b)` | Comparison as string (no ANSI) |

**Color support** (via environment variables):
- `PYPROBE_COLOR`: `auto` (default), `always`, `never`
- `PYPROBE_COLOR_MODE`: `normal` (default), `colorblind`

When `auto` mode is used, ANSI codes are suppressed if stdout is not a TTY or `NO_COLOR` is set.

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

## Public API

The top-level `pyprobe/__init__.py` exports:

```python
from .core import Pointer
from .core.common import (
    PyProbeError,
    PyProbeFatalError,
    PyProbeIntegrityError,
    PyProbeSafetyError,
    PyProbeSecurityError,
    PyProbeWarning,
)
from .core.log import get_ring
from .core.ux import explain, audit, audit_str, to_dict, to_json, compare, compare_str

def pin(obj: Any, safe: bool = True) -> Pointer: ...
def pin_addr(addr: int, safe: bool = True) -> Pointer: ...
```

**Note**: `__all__` is not defined. This is intentional — the package exposes only documented symbols, and wildcard imports (`from pyprobe import *`) are not expected. Adding `__all__` would be stylistic, not functional.

---

## Performance Considerations

1. **Type name caching**: `_TYPE_NAME_CACHE` avoids repeated type lookups
2. **Lazy dummy discovery**: `_get_dummy_ptr()` only runs when needed
3. **Direct memory access**: No Python API overhead for reading
4. **Minimal object creation**: Lenses are applied in-place, not copied

> **Note on `_TYPE_NAME_CACHE`**: This is an unbounded dict mapping `type_id → type_name`. In practice, it plateaus around a few thousand entries (one per unique type in the process). For long-running processes with dynamic class creation, consider periodic cache clearing. This is a bounded cache with a soft limit, not a memory leak.

---

## Memory Ownership

One of the hardest problems in CPython tooling is **memory ownership**. When PyProbe reads or mutates memory, it must understand who owns that memory and what constraints apply.

### Ownership Categories

| Category | Description | Can Mutate? | Detection |
|----------|-------------|-------------|-----------|
| **Borrowed Reference** | Temporary reference from container (e.g., `list[i]`) | With care | Refcount check |
| **Owned Reference** | Exclusive reference (refcount = 1) | Yes | Refcount == 1 |
| **Immortal Object** | Never deallocated (PEP 683) | No | Refcount > 2^30 |
| **Interned Object** | Shared singleton (strings, small ints) | No | Type-specific flags |
| **Shared Object** | Multiple references (refcount > 1) | With extreme care | Refcount > 1 |

### How PyProbe Models Ownership

PyProbe uses a **three-tier safety model** (see [SAFETY_MODEL.md](./SAFETY_MODEL.md)):

1. **Hard blocks** (`PyProbeSecurityError`): Immutable objects, interned strings, live bytecode — never bypassable
2. **Soft blocks** (`PyProbeSafetyError`): Shared objects, cached ints — bypassable with `safe=False`
3. **No check**: Owned objects with sole references — safe to mutate

The `safe` parameter controls whether soft blocks fire:
```python
# This will raise PyProbeSafetyError if x is a cached int (0-256)
ptr = pyprobe.pin(x)
ptr.mutate_int(999)

# This bypasses PyProbeSafetyError but not PyProbeSecurityError
ptr = pyprobe.pin(x, safe=False)
ptr.mutate_int(999)
```

### Limitations

- **Borrowed references** are not explicitly tracked — PyProbe relies on the caller to ensure the container outlives the mutation
- **Immortal object detection** is approximate (refcount threshold) — may have false positives on very large refcounts
- **Interned string detection** requires type-specific logic per lens

---

## Failure Philosophy

PyProbe's design reflects a specific philosophy about failure:

> **Never corrupt memory. Let advanced users do dangerous things.**

This creates a tension between safety and flexibility:

### The Spectrum

```
Safe ◄────────────────────────────────────────────────► Dangerous

  │                    │                    │
  ▼                    ▼                    ▼
PyProbeSecurityError  PyProbeSafetyError  safe=False
(no bypass)           (bypassable)        (no checks)
```

### Design Decisions

1. **Hard blocks are never bypassable**: If PyProbe detects an operation that would corrupt memory (e.g., mutating an interned string), it raises `PyProbeSecurityError` and there is no way to override this. This is non-negotiable.

2. **Soft blocks are advisory**: `PyProbeSafetyError` warnings (e.g., "object has multiple references") can be bypassed with `safe=False`. The assumption is that the user has verified safety manually.

3. **Rollback is best-effort**: When a mutation fails, PyProbe attempts to restore the original state. However, this is not atomic — if the process crashes mid-rollback, memory may be corrupted. This is an explicit tradeoff: atomic rollback would require OS-level support (e.g., `mprotect`) and is not portable.

4. **No guarantees on concurrent access**: PyProbe does not use locks or atomics. Mutations are not thread-safe. The documentation states this clearly, and `comprehensive_safety_check` warns about shared references.

### Why This Philosophy?

PyProbe is a **systems debugging tool**, not a production runtime. Its users are:
- CPython internals developers
- Security researchers
- Performance engineers
- Debuggers and profilers

These users need the ability to violate invariants for investigation. PyProbe provides guardrails but not handcuffs.

---

## Future Extensibility

### Interpreter Support

The offset discovery system was designed with portability in mind:

| Interpreter | Status | Notes |
|-------------|--------|-------|
| **CPython 3.12+** | Supported | Primary target, all features |
| **CPython 3.10-3.11** | Partial | Some offsets differ, tested |
| **PyPy** | Not supported | Different memory model (JIT) |
| **GraalPython** | Not supported | Different memory model (Java) |
| **Debug CPython** | Not supported | Different struct layouts |
| **Custom interpreters** | Not supported | Would require custom lenses |

**Why CPython only?**

PyProbe reads CPython's internal struct layouts directly via `ctypes`. These layouts are:
- Version-specific (fields change between releases)
- Implementation-specific (PyPy uses completely different structures)
- Not part of Python's public API

The offset discovery system (`offset_discovery.py`) probes memory to discover layout at runtime, which makes it resilient to minor version changes. However, it cannot adapt to fundamentally different memory models.

### Adding New Types

To add support for a new type (e.g., `collections.deque`):

1. **Create a lens** in `src/pyprobe/raw/lenses/deque_lens.py`
2. **Add an extractor** in `engine.py`
3. **Register in the dispatcher** (`_extractors` dict)
4. **Add tests** in `tests/test_collections.py`

If the type is not in the dispatcher, `pull_data_from_address` returns `f"<{type_name} @ {hex(addr)}>"` — a graceful fallback.

### Plugin Architecture (Conditional)

A plugin system could allow external packages to register extractors:

```python
# Hypothetical future API
import pyprobe
from pyprobe.plugins import register_extractor

@register_extractor("collections.deque")
def extract_deque(addr, visited, depth):
    ...
```

**When would this be useful?**
- If supported types exceed ~30 (currently ~25)
- If third-party packages want to add extractors without modifying PyProbe
- If PyProbe is used as a library by other tools

**Current assessment**: Not needed. The centralized engine is easier to audit, debug, and reason about. Plugin systems introduce registration, dynamic dispatch, and abstraction layers that increase cognitive load. For a systems debugging tool, auditability > modularity.

**Recommendation**: Leave as "worth reconsidering if supported types exceed N" rather than a concrete recommendation. The current design is intentional, not accidental.

---

## Architectural Risk Score

| Area | Risk | Rationale |
|------|------|-----------|
| **Offset Discovery** | Low | Probe-and-match is resilient; failure is loud (import-time crash) |
| **Lenses** | Low | Pure data structures, no logic, no state |
| **Safety Model** | Medium | Three-tier system is sound, but edge cases exist (immortal detection) |
| **Transactions** | Medium | Best-effort rollback is inherently racy; test coverage is thin |
| **Engine (Pointer)** | Medium | 956 LOC god object, but intentional for auditability |
| **UX Module** | Low | Read-only, no mutation, no state |

### Key Risks

1. **CPython version drift**: Offsets discovered at runtime may break with CPython updates. Mitigation: probe-and-match fails loudly.

2. **Concurrent mutation**: No thread-safety guarantees. Mitigation: documented, `comprehensive_safety_check` warns.

3. **Rollback failure**: Best-effort rollback may leave memory corrupted if process crashes mid-rollback. Mitigation: use transactions only for batch operations, not individual mutations.

4. **Test coverage gaps**: Transaction tests bypass safety layer (`safe=False`), property-based testing absent. Mitigation: add tests before v2.0.

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

### Class-Level Extractor Table

The `_extractors` dict is currently defined per-instance in `Pointer.__init__`. This is intentional but suboptimal:

```python
# Current: rebuilt per instance
class Pointer:
    def __init__(self, ...):
        self._extractors = {
            'int': self._extract_int,
            'float': self._extract_float,
            ...
        }
```

**Could it be class-level?**

Yes — all extractors are bound methods that only depend on `self`. Moving to class level would:
- Reduce memory allocation (one dict vs. per-instance)
- Improve cache locality
- Be semantically equivalent

**Why hasn't it been done?**

The current design was chosen for:
- Simplicity (no descriptor protocol complexity)
- Future flexibility (instance-specific overrides possible)
- Auditability (clear that extractors are per-Pointer)

**Recommendation**: Move to class level before v2.0. Verify that no extractor uses closures or captures from `__init__` (none do currently).

---

## Dependencies

**Runtime**: None (pure stdlib, uses `ctypes`)

**Development**: 
- Python 3.12+ (required)
- pytest (optional, for testing)

---

## Architectural Decision Records (ADRs)

The following key decisions should be recorded as ADRs for future contributors:

### ADR-001: Why Pointer is Centralized (Not Plugin-Based)

**Context**: The `Pointer` class contains all extractors in a single 956-line file.

**Decision**: Keep centralized for auditability.

**Rationale**: Low-level memory libraries require careful reasoning about correctness. Plugin systems introduce dynamic dispatch, registration complexity, and harder debugging. For a systems debugging tool, auditability > modularity.

**Consequences**: Adding new types requires modifying `engine.py`. This is acceptable for ~25 types.

### ADR-002: Why Offset Discovery Happens at Import Time

**Context**: `offset_discovery.py` probes memory to discover struct layouts at import time.

**Decision**: Discover at import time, not first use.

**Rationale**: Fails loudly on unsupported CPython versions. No partial initialization states. Users know immediately if PyProbe won't work.

**Consequences**: Import is slower (~10ms), but this is a one-time cost.

### ADR-003: Why Rollback is Best-Effort

**Context**: `snapshot()` + `verify()` attempt to restore state on mutation failure.

**Decision**: Best-effort rollback, not atomic.

**Rationale**: Atomic rollback would require OS-level support (`mprotect`, `mmap`) and is not portable. PyProbe is a debugging tool, not a production runtime.

**Consequences**: If the process crashes mid-rollback, memory may be corrupted. Users should use transactions for batch operations only.

### ADR-004: Why Hard and Soft Safety Checks are Separated

**Context**: `PyProbeSecurityError` (hard) vs `PyProbeSafetyError` (soft) have different bypass semantics.

**Decision**: Three-tier safety model.

**Rationale**: Some operations are always wrong (mutating interned strings). Others are conditionally safe (mutating shared objects with manual verification). The `safe` parameter controls only the soft tier.

**Consequences**: Users can bypass soft blocks but not hard blocks. This is intentional — hard blocks protect against memory corruption.
