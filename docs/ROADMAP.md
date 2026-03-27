# PyProbe Roadmap

This document outlines the project phases, timeline, research goals, and publication strategy.

---

## Project Vision

**PyProbe** aims to be:

1. **A research tool** - For studying CPython memory internals
2. **A practical utility** - For debugging, profiling, and low-level optimization
3. **A published contribution** - To the Python tooling and PL research community

---

## Project Phases

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 1: X-RAY (Complete)                                      │
│  Read-only memory introspection                                 │
│  "We can see inside Python objects"                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 2: SCALPEL (In Progress)                                 │
│  Controlled memory mutation                                     │
│  "We can perform precise operations on memory"                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 3: SURGEON'S TOOLKIT (Future)                            │
│  High-level operations, shared memory, IPC                      │
│  "We can build applications on top of this"                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: X-Ray (Complete)

### Deliverables

- [x] Core `Pointer` class with memory introspection
- [x] Support for all major built-in types (int, float, str, bytes, list, tuple, dict, set)
- [x] Cycle detection and depth limiting
- [x] Safety guards for invalid addresses
- [x] Multi-encoding string support (ASCII, Latin-1, UCS-2, UCS-4)
- [x] Tombstone detection in dicts/sets
- [x] Interactive REPL tool
- [x] Reference count tracker
- [x] Test suite

### What We Learned

1. CPython's memory layout is well-documented but version-specific
2. Pure Python introspection via ctypes is viable and performant
3. Safety guards are essential for preventing crashes
4. The dual-layer (headers/lenses) abstraction works well

---

## Phase 2: Scalpel (Current Focus)

### Goals

1. **Implement write primitives** - The ability to mutate memory safely
2. **Define safety model** - Document when mutation is safe/unsafe
3. **Build validation framework** - Pre-mutation checks
4. **Extend test suite** - Cover mutation scenarios

### Deliverables

| Deliverable | Status | Priority |
|-------------|--------|----------|
| Safety model documentation | Complete | Critical |
| `is_safe_to_mutate()` function | Not started | Critical |
| `poke(offset, value)` - raw write | Not started | High |
| `mutate_int(new_value)` | Not started | High |
| `mutate_float(new_value)` | Not started | High |
| `mutate_list_element(idx, val)` | Not started | High |
| `mutate_dict_value(key, val)` | Not started | High |
| Refcount management helpers | Not started | High |
| CPython implementation guard | Not started | Medium |
| Safety test suite | Not started | High |

### Timeline (Estimated)

```
Month 1-2: Core Mutation
├── Week 1-2: Implement safety checks
├── Week 3-4: Implement basic poke()
├── Week 5-6: Type-specific mutators
└── Week 7-8: Refcount management

Month 3: Testing & Hardening
├── Week 9-10: Comprehensive safety tests
├── Week 11-12: Edge cases, version compatibility
```

---

## Phase 3: Surgeon's Toolkit (Future)

### Goals

1. **Shared memory support** - Attach to external memory regions
2. **IPC primitives** - Zero-copy communication between processes
3. **Hot-patching** - Runtime code/data modification
4. **Memory mapping** - Map files/buffers to Python objects

### Potential Deliverables

| Deliverable | Description |
|-------------|-------------|
| `attach_shm(name)` | Attach to POSIX shared memory |
| `SharedPointer` | Pointer that works across processes |
| `MemoryMappedObject` | Python object backed by mmap |
| Process communication demo | Two Python processes sharing data |
| JNI bridge prototype | Java ↔ Python zero-copy (stretch goal) |

### Timeline (Estimated)

```
Month 4-5: Shared Memory
├── mmap integration
├── Shared pointer abstraction
└── IPC demonstration

Month 6+: Applications
├── Case studies
├── Performance benchmarks
└── Documentation
```

---

## Research Goals

### Primary Research Questions

1. **What are the safety invariants for CPython memory mutation?**
   - When is it safe to mutate?
   - What checks are necessary and sufficient?

2. **What is the performance cost of safe mutation vs. Python APIs?**
   - Measure overhead of safety checks
   - Compare to native Python operations

3. **Can we build useful applications on memory-level access?**
   - Shared memory IPC
   - Hot-patching
   - Memory optimization

### Secondary Research Questions

4. How has CPython's memory layout evolved across versions?
5. What is the actual memory overhead of Python objects?
6. Can non-invasive introspection replace C extensions for some use cases?

---

## Publication Strategy

### Target Venues (in order of submission)

| Venue | Type | Timeline | Focus |
|-------|------|----------|-------|
| **arXiv** | Preprint | Month 4-5 | Establish priority |
| **JOSS** | Journal | Month 5-6 | Tool publication |
| **SoftwareX** | Journal | Month 6-7 | Software + validation |
| **SIGPLAN workshop** | Conference | Month 8+ | Research contribution |

### Paper Structure (Draft)

```
1. Introduction
   - Python's opaque memory model
   - The need for introspection and controlled mutation
   - Our contributions

2. Background
   - CPython object model
   - Memory allocation (pymalloc)
   - Related work (pympler, objgraph, tracemalloc)

3. PyProbe: Design and Implementation
   - Architecture (layers, patterns)
   - X-Ray: Read capabilities
   - Scalpel: Write capabilities
   - Safety model

4. Safety Analysis
   - Invariants for safe mutation
   - Detection mechanisms
   - What can go wrong

5. Evaluation
   - Memory overhead measurements
   - Performance benchmarks
   - Case study: Shared memory IPC

6. Discussion
   - Limitations
   - Version compatibility
   - Future work

7. Related Work
   - Memory profilers
   - Debuggers
   - FFI tools

8. Conclusion
```

### Key Claims to Support

1. **Novelty**: Pure Python introspection + mutation framework with documented safety model
2. **Correctness**: Safety checks prevent common corruption scenarios
3. **Usefulness**: Practical applications (IPC, debugging, research)
4. **Performance**: Competitive with or better than existing approaches

---

## Experiments to Run

### Experiment 1: Memory Overhead

**Goal**: Quantify Python's object overhead across types.

**Method**:
```python
types_to_measure = [int, float, str, bytes, list, tuple, dict, set]
sizes = [0, 1, 10, 100, 1000, 10000]

for type_ in types_to_measure:
    for size in sizes:
        obj = create_object(type_, size)
        actual_bytes = measure_with_pyprobe(obj)
        logical_bytes = calculate_logical_size(obj)
        overhead = actual_bytes - logical_bytes
        # Record: type, size, actual, logical, overhead
```

**Output**: Tables and graphs showing overhead by type and size.

### Experiment 2: Version Comparison

**Goal**: Document memory layout changes across Python versions.

**Method**:
- Run PyProbe on Python 3.12, 3.13, 3.14
- Record offsets, struct sizes, field encodings
- Document differences

**Output**: Compatibility matrix, version-specific notes.

### Experiment 3: Safety Model Validation

**Goal**: Verify that safety checks prevent corruption.

**Method**:
- Attempt mutations on unsafe targets (interned, cached, shared)
- Verify rejection
- Attempt mutations on safe targets
- Verify success without corruption

**Output**: Test results, coverage metrics.

### Experiment 4: Performance Benchmarks

**Goal**: Compare PyProbe to standard Python APIs and C extensions.

**Method**:
```python
operations = [
    ("read dict value", lambda d, k: d[k], lambda d, k: pyprobe_read_dict(d, k)),
    ("write dict value", lambda d, k, v: d.__setitem__(k, v), lambda d, k, v: pyprobe_write_dict(d, k, v)),
    # ... more operations
]

for name, python_op, pyprobe_op in operations:
    python_time = benchmark(python_op)
    pyprobe_time = benchmark(pyprobe_op)
    # Record: operation, python_time, pyprobe_time, ratio
```

**Output**: Performance comparison tables.

### Experiment 5: Shared Memory IPC

**Goal**: Demonstrate zero-copy IPC between Python processes.

**Method**:
- Create shared memory region
- Process A writes data via PyProbe
- Process B reads data via PyProbe
- Measure throughput vs. pickle/multiprocessing.Queue

**Output**: Throughput comparison, latency measurements.

---

## Milestones

| Milestone | Target Date | Deliverables |
|-----------|-------------|--------------|
| Safety model complete | Month 1 | SAFETY_MODEL.md finalized |
| Scalpel MVP | Month 2 | Basic mutation working |
| Test suite complete | Month 3 | All mutation tests passing |
| arXiv submission | Month 4-5 | Paper draft complete |
| JOSS submission | Month 5-6 | Tool polished, docs complete |
| Shared memory demo | Month 6 | IPC working |
| SoftwareX submission | Month 7 | Validation complete |

---

## Team Responsibilities (Template)

When the team grows, assign ownership:

| Area | Owner | Backup |
|------|-------|--------|
| Core engine | TBD | TBD |
| Safety model | TBD | TBD |
| Testing | TBD | TBD |
| Documentation | TBD | TBD |
| Benchmarks | TBD | TBD |
| Paper writing | TBD | TBD |

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| CPython internals change | High | Version-specific code paths, CI on multiple versions |
| Safety model incomplete | High | Conservative defaults, extensive testing |
| Performance worse than expected | Medium | Optimize hot paths, document when to use |
| Paper rejected | Medium | Multiple venues, iterate on feedback |
| Team availability | Medium | Good documentation, modular design |

---

## Success Criteria

### For the Tool

- [ ] Works on Python 3.12, 3.13, 3.14
- [ ] Zero segfaults in normal use
- [ ] Safety checks catch all known unsafe mutations
- [ ] Pip installable
- [ ] Comprehensive documentation

### For the Research

- [ ] Paper accepted to at least one venue
- [ ] Novel contribution recognized (safety model)
- [ ] Useful to at least some Python developers
- [ ] Cited by others (long-term)

---

## How to Contribute to the Roadmap

This roadmap is a living document. To propose changes:

1. Open an issue describing the proposed change
2. Discuss with the team
3. Update this document via PR
4. Get approval from project lead

---

## Appendix: Publication Requirements

### arXiv

- [ ] LaTeX source
- [ ] Figures in PDF format
- [ ] No review process, just upload
- [ ] Can update with new versions

### JOSS

- [ ] Software must be open source
- [ ] Must have documentation
- [ ] Must have automated tests
- [ ] Short paper (1-2 pages) describing software
- [ ] Review focuses on software quality

### SoftwareX

- [ ] Software must be significant
- [ ] Paper describes software + validation
- [ ] Longer than JOSS (5-10 pages)
- [ ] Peer reviewed

### ACM SIGPLAN Workshops

- [ ] Novel research contribution
- [ ] Rigorous evaluation
- [ ] 8-12 page paper
- [ ] Peer reviewed
- [ ] Examples: ICOOOLPS, Meta, DLS
