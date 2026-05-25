# Future Plans

**Up**: [PyProbe](../PyProbe.md)

---

## Phase 2 — SCALPEL (Current)

### Safe in-place memory mutation

Build the write layer for PyProbe. The goal: mutate any Python object's memory in-place without crashing.

**Architecture:**
- Surgical transaction model — validate before write, verify after write, rollback on failure
- Whitelist of safe-to-mutate fields (data payload) vs protected fields (type pointers, refcount machinery)
- Automatic refcount management when replacing pointer fields
- Signal handler to catch segfaults during experimental mutations

### Refcount hijacking — permanent pinning

Every CPython object has `ob_refcnt` at offset +0. When it hits 0, the object is freed. PyProbe can hijack this:

Set `ob_refcnt` to a sentinel value (`UINT64_MAX` or a magic constant). Teach PyProbe (and any bridge that uses it) to skip freeing objects with that sentinel. The object stays alive permanently — no GC, no re-allocation.

**Use case:** Pin Python objects in memory so other languages (Java via PyJx, Rust, C) can hold stable pointers. Without this, a GC cycle invalidates every foreign pointer.

**But this creates a race condition.** Two runtimes accessing the same pinned object concurrently can corrupt data or read stale values. The fix: a per-object read-write lock stored in a small header prepended to pinned memory.

**Thread safety protocol (to be implemented in PyProbe, inherited by all bridges):**
- Per-object lock (read/write semantics)
- Writers block readers, or vice versa depending on tradeoff
- Same protocol used for the sentinel refcount itself (preventing double-free on either runtime)
- Lock overhead only applies to pinned objects — unpinned objects are unaffected

**Success criteria:**
- [ ] `pin(obj).write(field, value)` works for primitives (int, float)
- [ ] `pin(obj).write(field, value)` works for collections (list items, dict entries)
- [ ] In-place mutation survives GC cycles
- [ ] Invalid mutations fail gracefully instead of crashing
- [ ] Rollback restores original state on failure

---

## Phase 2.5 — Generalization

### Fix the jank

PyProbe's current problems are version-specific hardcoding and unreliable dict reads. Phase 2.5 exists to fix these before building applications.

### 2.5a — Runtime probing layer

```
On import:
  1. Detect CPython version
  2. Create test objects for each type
  3. Scan memory for struct boundaries
  4. Build offset table dynamically
  5. Cache for the session
```

Instead of `HEADER_SIZE = 16`, the probing layer discovers PyObject_HEAD at runtime. Instead of hardcoded dict entry strides, it scans the keys table and determines the layout programmatically.

**Approach ideas:**
- Use sentinel values to find field boundaries
- Compare known values against memory to derive offsets
- Leverage `ctypes.alignment` + known sizes to validate guesses
- Fall back to a hardcoded database of known CPython version layouts

**Success criteria:**
- [ ] PyProbe works on CPython 3.12, 3.13, 3.14 without code changes
- [ ] Reports unsupported versions with a clear error message
- [ ] Self-calibrates in < 1 second on import

### 2.5b — Dict read reliability

Rewrite the dict extraction to handle all three table layouts robustly:

- Detect combined vs split vs unicode-only from the dk_kind field
- Verify tombstone/dummy pointer detection for each layout
- Test against edge cases: empty dicts, 1-element dicts, high-collision tables, key-sharing dicts
- Add comprehensive dict tests to the test suite

**Success criteria:**
- [ ] All three dict layouts read correctly
- [ ] Tombstones correctly identified in all layouts
- [ ] No false positives on valid entries
- [ ] 100% pass rate on corpus of real-world dicts (json data, class dicts, module dicts)

### 2.5c — Safe mutation protocol

Build the transaction model before opening write access to users:

- `begin_transaction()` — snapshot current state
- `mutate(address, field, value)` — apply change
- `validate()` — check object integrity
- `commit()` — finalize changes, drop snapshot
- `rollback()` — restore snapshot, log failure

This isolates crashes during development and gives users a safety net when PyProbe inevitably mutates something it shouldn't.

---

## Phase 3 — TOOLKIT

### Applications built on X-RAY + SCALPEL

Once we can read and write safely, build the tools that make PyProbe useful.

### 3a — PyJx (Python → Java bridge)

The first consumer. Uses PyProbe to pin Python objects and hand their addresses to a JVM via JNI. The JVM reads/writes Python memory directly — no serialization, no FFI marshalling.

**Requires from PyProbe:**
- Static memory pinning (prevent GC from moving objects)
- Refcount management across runtimes
- Thread-safe mutation protocol

### 3b — Memory leak detector

Use X-RAY to scan all live Python objects. Report:
- Objects with unexpectedly high refcounts
- Cycles that should be collected but aren't
- Dicts with excessive tombstone ratios
- Strings that could be interned

### 3c — ML training optimizer

The original use case. In-place gradient updates without re-allocation.

Instead of:
```python
for param in model.parameters():
    param.data -= lr * param.grad  # New allocation every time
```

```python
from pyprobe import pin
for param in model.parameters():
    pin(param.data).write_in_place(lambda x: x - lr * param.grad)
```

Potential speedup for training loops: 2-10x on memory-bound operations, depending on model size.

### 3d — Mutation fuzzer

Systematically mutate object memory to test interpreter robustness. Useful for CPython core development and security research.

---

## Phase 4 — Cross-Runtime

### Thread safety protocol

Design the coordination layer for multiple runtimes sharing memory:

- Lock registry: which runtime holds which memory regions
- Read/write locks at the object level
- Heartbeat mechanism to detect dead runtimes and release their pins
- Dead pointer detection and graceful invalidation

### C extension fallback

For performance-critical operations, extract the ctypes overlay logic into a small C extension. The Python API stays the same — only the backend changes.

**C extension handles:**
- Atomic memory reads/writes
- Allocation hook interception
- Signal handling for protection
- Performance-sensitive bulk operations

**ctypes layer retains:**
- User-facing API
- Type system and lenses
- Safety validation
- Version probing

This gives us the flexibility of pure Python with the option to drop to C when needed.

---

## Publication Roadmap

| Venue | Target | Material |
|-------|--------|----------|
| arXiv | Phase 2 complete | Technical paper + benchmark |
| JOSS | Phase 3 stable | Software paper + docs |
| PyCon / EuroPython | Phase 3 released | Talk + demo |
| ACM SIGPLAN | Phase 4 designed | Research paper on cross-runtime memory |

---

## The Long Game

PyProbe → PyJx → Nexus → COBALT.

Each layer depends on the one below. PyProbe is the foundation — solve memory, and everything above becomes possible.

**The question PyProbe answers:** "What if Python had C's memory model without losing Python's expressiveness?"

**The answer:** You'd have Python that talks to any language at native speed, mutates in-place without copying, and still feels like Python. That's what we're building.
