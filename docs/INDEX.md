# PyProbe Documentation

Welcome to the PyProbe documentation. This project is a research-grade toolkit for CPython memory introspection and manipulation.

## What is PyProbe?

PyProbe is evolving through two phases:

| Phase | Codename | Description | Status |
|-------|----------|-------------|--------|
| **Phase 1** | X-Ray | Read-only memory introspection | Complete |
| **Phase 2** | Scalpel | Controlled memory mutation | In Development |

The goal: understand Python's memory model deeply enough to **read it**, **document it**, and eventually **manipulate it safely**.

---

## Documentation Map

### For Everyone

| Document | Description |
|----------|-------------|
| [README](../README.md) | Project overview and quick start |
| [ROADMAP](./ROADMAP.md) | Project phases, timeline, and research goals |
| [CONTRIBUTING](./CONTRIBUTING.md) | How to contribute, team onboarding |

### For Developers

| Document | Description |
|----------|-------------|
| [ARCHITECTURE](./ARCHITECTURE.md) | System design, code organization, design patterns |
| [CPYTHON_MEMORY](./CPYTHON_MEMORY.md) | CPython internals reference (the knowledge base) |
| [SAFETY_MODEL](./SAFETY_MODEL.md) | What's safe to mutate, what isn't, and why |

### For Researchers

| Document | Description |
|----------|-------------|
| [ROADMAP](./ROADMAP.md) | Research questions and publication targets |
| [SAFETY_MODEL](./SAFETY_MODEL.md) | The intellectual core of our contribution |

---

## Quick Orientation

### If You're New to the Project

1. Read the [README](../README.md) for the big picture
2. Read the [ROADMAP](./ROADMAP.md) to understand where we're going
3. Read [CONTRIBUTING](./CONTRIBUTING.md) to get set up

### If You're Implementing Features

1. Read [ARCHITECTURE](./ARCHITECTURE.md) to understand the codebase
2. Read [CPYTHON_MEMORY](./CPYTHON_MEMORY.md) for the memory layouts you'll work with
3. Read [SAFETY_MODEL](./SAFETY_MODEL.md) before writing ANY mutation code

### If You're Doing Research/Writing

1. Read [SAFETY_MODEL](./SAFETY_MODEL.md) - this is our core contribution
2. Read [ROADMAP](./ROADMAP.md) for research questions and publication strategy
3. Read [CPYTHON_MEMORY](./CPYTHON_MEMORY.md) for technical accuracy

---

## Key Concepts

### The Analogy

Think of PyProbe as medical imaging and surgery tools:

- **Phase 1 (X-Ray)**: We can see inside Python objects without touching them
- **Phase 2 (Scalpel)**: We can perform precise operations on the memory

### The Core Question

> **Can we build a system that safely mutates Python objects at the memory level, with documented invariants and safety guarantees?**

This question drives everything we do.

### Why This Matters

1. **Practical**: Zero-copy IPC, shared memory, hot-patching
2. **Educational**: Deep understanding of CPython internals
3. **Research**: Novel contribution to Python tooling literature

---

## Getting Help

- Check the relevant documentation first
- Look at existing code in `src/pyprobe/` for examples
- Look at tests in `tests/` for usage patterns
- Ask your team lead or open an issue

---

## Document Status

| Document | Status | Last Updated |
|----------|--------|--------------|
| INDEX.md | Complete | 2024 |
| ARCHITECTURE.md | Complete | 2024 |
| CPYTHON_MEMORY.md | Complete | 2024 |
| SAFETY_MODEL.md | Complete | 2024 |
| ROADMAP.md | Complete | 2024 |
| CONTRIBUTING.md | Complete | 2024 |
