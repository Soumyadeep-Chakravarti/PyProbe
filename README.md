# PyProbe

**PyProbe** is a research-grade toolkit for CPython memory introspection and controlled manipulation. It provides direct access to Python's internal memory structures, enabling both observation (X-Ray) and eventually safe modification (Scalpel) of runtime objects.

> **Research Project** - Targeting publication in arXiv, JOSS, SoftwareX, and ACM SIGPLAN venues.

---

## The Vision

```
Phase 1: X-RAY      →    Phase 2: SCALPEL     →    Phase 3: TOOLKIT
Read memory              Write memory              Build applications
Inspect objects          Mutate objects            Shared memory IPC
Diagnose                 Operate                   Zero-copy bridges
[COMPLETE]               [IN PROGRESS]             [FUTURE]
```

We're building the tools to truly understand and control Python's memory - with documented safety guarantees.

---

## Quick Start

```python
import pyprobe

# Pin an object to inspect its memory
x = {"name": "Alice", "scores": [95, 87, 92]}
ptr = pyprobe.pin(x)

# X-Ray: See what's really in memory
ptr.examine()

# Extract the actual data
data = ptr.xray()
print(data)  # {'name': 'Alice', 'scores': [95, 87, 92]}
```

---

## What Can PyProbe Do?

### Phase 1: X-Ray (Complete)

Read Python objects at the memory level:

| Capability | Description |
|------------|-------------|
| **Object Inspection** | See refcount, type pointer, internal fields |
| **Data Extraction** | Pull values directly from memory addresses |
| **Type Support** | int, float, str, bytes, list, tuple, dict, set |
| **Cycle Detection** | Handle self-referential structures safely |
| **Multi-Encoding Strings** | ASCII, Latin-1, UCS-2, UCS-4 |
| **Tombstone Detection** | Skip deleted entries in dicts/sets |

```python
# Inspect a complex nested structure
data = {
    "users": [
        {"name": "Alice", "active": True},
        {"name": "Bob", "active": False}
    ],
    "count": 2
}

ptr = pyprobe.pin(data)
extracted = ptr.xray()  # Recursively extracts everything
```

### Phase 2: Scalpel (In Development)

Controlled memory mutation with safety guarantees:

| Capability | Status |
|------------|--------|
| Safety model | Documented |
| Pre-mutation checks | Planned |
| Integer mutation | Planned |
| Float mutation | Planned |
| List element swap | Planned |
| Dict value update | Planned |

### Phase 3: Surgeon's Toolkit (Future)

High-level applications:

- Shared memory IPC (zero-copy between processes)
- Memory-mapped objects
- Hot-patching
- Foreign function bridges

---

## Why PyProbe?

### For Researchers

- Study CPython's memory model empirically
- Document version-specific changes (3.12 → 3.14)
- Publish findings on memory overhead and safety

### For Developers

- Debug memory issues at the lowest level
- Build zero-copy IPC mechanisms
- Understand what Python is really doing

### For Educators

- Teach how interpreters manage memory
- Visualize object layouts
- Demonstrate reference counting

---

## Installation

```bash
# Requires Python 3.12+ (64-bit)
pip install pyprobe

# Or from source
git clone <repo-url>
cd PyProbe
pip install -e .
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/INDEX.md](docs/INDEX.md) | Documentation home |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design |
| [docs/CPYTHON_MEMORY.md](docs/CPYTHON_MEMORY.md) | CPython internals reference |
| [docs/SAFETY_MODEL.md](docs/SAFETY_MODEL.md) | When mutation is safe |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Project phases and timeline |
| [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) | How to contribute |

---

## Tools

PyProbe includes debugging utilities:

```bash
# Interactive memory exploration REPL
python tools/explorer_repl.py

# Reference count tracker
python tools/leak_tracker.py
```

---

## Safety

> **Warning**: This project involves direct memory access. Misuse can cause segmentation faults.

PyProbe implements multiple safety layers:

- **Address validation** - Rejects invalid/unaligned addresses
- **Cycle detection** - Prevents infinite recursion
- **Depth limiting** - Caps recursion at 100 levels
- **Type checking** - Validates object headers

For mutation (Phase 2), additional safety:

- **Refcount checks** - Prevents mutating shared objects
- **Interning detection** - Blocks mutation of interned strings
- **Small int cache** - Protects cached integers (-5 to 256)
- **Immortal objects** - Respects PEP 683 immortality

See [SAFETY_MODEL.md](docs/SAFETY_MODEL.md) for the complete safety analysis.

---

## Research Goals

We're investigating:

1. **Safety invariants** - When is CPython memory mutation safe?
2. **Memory overhead** - What's the real cost of Python objects?
3. **Version evolution** - How has CPython's layout changed?
4. **Practical applications** - Can this enable new use cases?

### Target Publications

- **arXiv** - Preprint for priority
- **JOSS** - Journal of Open Source Software
- **SoftwareX** - Software with validation
- **ACM SIGPLAN** - Workshop on implementation/runtime

---

## Requirements

- **Python**: 3.12, 3.13, 3.14+ (64-bit only)
- **Platform**: Linux, macOS, Windows
- **Dependencies**: None (pure stdlib with ctypes)

---

## Project Status

| Component | Status |
|-----------|--------|
| Core introspection | Stable |
| Type extractors | Complete |
| Safety guards | Complete |
| Documentation | Complete |
| Mutation (Scalpel) | In Development |
| Shared memory | Planned |
| Publication | In Progress |

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for:

- Setup instructions
- Code style guide
- Testing requirements
- PR process

---

## License

[TBD - likely MIT or Apache 2.0]

---

## Acknowledgments

- The CPython core developers for a well-documented runtime
- The Python community for inspiration and feedback

---

## Contact

[TBD - add contact info, issue tracker, etc.]
