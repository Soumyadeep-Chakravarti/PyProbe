# PyProbe — Solve Python's Memory Problem

**Repository:** [github.com/Soumyadeep-Chakravarti/PyProbe](https://github.com/Soumyadeep-Chakravarti/PyProbe)
**Status:** Phase 2 / 3 (X-Ray done → Scalpel in progress)
**Target:** arXiv, JOSS, SoftwareX, ACM SIGPLAN

---

## The Pitch

> Python lets you do this:
> ```python
> x = 1
> x = str(x)  # int → string, no problem
> ```
> 
> C and C++ can't do this because memory is allocated based on type — 4 bytes for int, 8 for float, 1 for char. Type conversion means re-allocating.
> 
> Python can do this because it **does not restrict itself to a memory location**. It does not follow the zero-copy rule. For every update to `x`, Python gives it a **new address** and destroys the old one.
> 
> This is great for type flexibility. **But it's terrible for performance.** Every time you update a variable, Python throws away the memory and allocates fresh.
> 
> In ML training, a single parameter gets updated billions of times. Each update = new allocation. That's billions of unnecessary memory operations.
> 
> **PyProbe solves this.** It gives you C-level memory control from Python — pin objects, read their internals, mutate in place without re-allocation. All with safety guardrails so you don't crash the interpreter.
> 
> — Soumyadeep, to the team

## What is PyProbe?

**Memory access of C + guardrails of Rust + simplicity of Python.**

A toolkit that lets you look inside live Python objects at the C memory level — refcounts, type pointers, internal hash tables, dict tombstones, everything. Then manipulate that memory in-place.

### The bigger picture — static memory = inter-language bridge

If a variable's type doesn't change, PyProbe pins it to a **static memory address**. That means C, Java, Rust, Go — any language — can hold a stable pointer to Python memory. No serialization, no copying, no FFI marshalling. True zero-copy inter-language operations.

You can pass **Python functions, classes, and objects** to other languages by memory reference — not by serializing them. A Java runtime can call a Python function directly. A Rust program can mutate a Python dict. A Go service can hold a reference to a Python class instance.

[Pyjx](../PyJx/PyJx.md) (Python↔Java bridge) is the first consumer — instead of marshalling data across the JNI boundary, both runtimes share the same memory. Nexus (polyglot message router) extends this to any connected language.

```python
from pyprobe import pin

d = {"key": "value"}
pin(d).examine()   # Shows raw dict internals
pin(d).xray()      # Extracts the Python value from memory
```

## The Problem — Python's Space Complexity

Languages like C allocate memory based on type. Python doesn't. Every time you update a variable:

1. Python allocates a **new** memory block
2. Writes the new value there
3. Destroys the **old** block

For a single `x = x + 1`, this is fine. For an ML model updating 7 billion parameters — it's **7 billion re-allocations**. Each one costs time and fragments memory.

The worst part: you're not asking for new memory. You're asking to change a value in place. Python just doesn't let you.

## The Solution — In-Place Memory Mutation

PyProbe gives you:
1. **Pin** any Python object to its memory address
2. **Read** its internal structure at the C level (refcounts, type pointers, data fields)
3. **Write** to that memory in-place — no re-allocation
4. **Safe** — guardrails prevent the kind of corruption that raw C memory access causes

## How it works

We use `ctypes` to overlay C struct definitions (PyObject, PyDictObject, PySetObject, etc.) onto live memory at runtime. No C extensions, no compilation, no gdb — pure Python.

Each Python type has a corresponding "lens" — a ctypes Structure that maps to its C layout:

```
Python object in memory
┌─────────────────────┐
│ PyObject_HEAD       │  ← 16 bytes (refcount + type pointer)
├─────────────────────┤
│ Type-specific data  │  ← Read through a "Lens"
└─────────────────────┘
```

### Supported types (Phase 1 — fully readable)

| Category | Types |
|----------|-------|
| Primitives | int, float, complex, bool, NoneType |
| Text/Bytes | str (ASCII/UTF-16/UTF-32), bytes, bytearray, memoryview |
| Collections | list, tuple, dict (split/combined), set, frozenset |
| Objects | range, slice, function, type, module, code, cell |
| Descriptors | property, staticmethod, classmethod |
| Built-ins | builtin_function_or_method, generator, enumerate |
| Errors | BaseException + all subclasses |

### Safety features

- 64-bit architecture guard
- Address validation (null/bad alignment checks)
- Cycle detection for recursive structures
- Depth limits on recursion
- Tombstone detection for dict/set internal slots
- Graceful error handling per slot

## Phase roadmap

```
Phase 1: X-RAY      →    Phase 2: SCALPEL     →    Phase 3: TOOLKIT
[DONE]                   [IN PROGRESS]             [FUTURE]
```

**X-RAY (done):** Read any Python object's memory. 50+ types supported — all builtins, functions, descriptors, exceptions.

**SCALPEL (in progress):** Safe in-place memory mutation. Change refcounts, swap pointers, edit internal fields. The hard part is knowing which mutations are safe — we're building a surgical transaction model with rollback.

### Recent Updates
- **Generalized offset discovery:** Instead of hardcoded offsets, PyProbe now dynamically discovers memory offsets for internal data structures (tuple items, list items, dict keys) at runtime, making it more robust across Python versions
- **Scalpel integration:** PyProbe now includes mutation capabilities from Scalpel, providing safe in-place memory modification through methods like `mutate_int`, `mutate_float`, `safe_list_swap`, and `safe_dict_value_swap`

**TOOLKIT (future):** Applications built on X-RAY + SCALPEL — ML training optimizers, leak detectors, mutation fuzzers, cross-runtime bridges.

## Stack position

```
COBALT           ← Future: 9-language orchestration
  └─ Nexus       ← Polyglot message router
       └─ PyJx   ← Python↔Java JNI bridge
            └─ PyProbe  ← YOU ARE HERE
```

PyProbe is the foundation. [Pyjx](../PyJx/PyJx.md) needs it for pointer stability. Nexus needs PyJx. Cobalt needs Nexus. This project unlocks everything above it.

## What's needed for Phase 2 (Scalpel)

- Understanding which CPython memory fields are safe to mutate
- Building a transaction model — make changes, validate, commit or rollback
- Testing against memory corruption
- Buffer overflow protection

## How to help

- Fork the repo: `github.com/Soumyadeep-Chakravarti/PyProbe`
- Pick an extractor, add tests
- Phase 2 contributions especially valuable — look at `core/pointer/engine.py`
- Ask questions if something's unclear

---

**Next:** [Pyjx](../PyJx/PyJx.md) — Python↔Java bridge
