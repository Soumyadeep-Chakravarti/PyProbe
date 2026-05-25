# Present Problems

**Up**: [PyProbe](../PyProbe.md)

> **Status as of 2026-05-14** — Phase 2 (Scalpel) in progress.
> These are the known issues that make PyProbe "janky" right now.

---

## 1. Hardcoded memory offsets

Every struct layout is hardcoded as `HEADER_SIZE = 16`, `offset + 32`, `offset + 48`, etc. These values are specific to CPython 3.12+ and will break on any version change. Even minor CPython releases can shift internal struct layouts — dict keys, string encodings, object headers all change between versions.

**What this causes:** PyProbe works on my machine (3.14) and breaks everywhere else. New Python install? Broken. Different architecture? Broken.

**What imaginary fix looks like:** A runtime probing layer that discovers struct layouts on import. Create known objects, scan memory for signatures, build an offset table dynamically.

**The current reality:** I haven't built the probing layer yet. It's the next big thing for Phase 2 or it blocks Phase 3 entirely.

---

## 2. Dict reads are unreliable

Dict internals are the most complex and version-sensitive part of CPython. Three table layouts exist:

- **Combined** — key-value pairs stored together in one table
- **Split** — keys in one table, values in an array (used for `__dict__` of class instances)
- **Unicode-only** — optimized for string keys

The dummy/tombstone pointer moves depending on the table layout. The index size varies with table capacity. Entry strides differ between Unicode (16 bytes) and general (24 bytes) tables.

**What this causes:** This is the biggest source of "sometimes it reads wrong." On certain dict layouts, the offsets misalign and we read garbage or miss entries entirely.

**What imaginary fix looks like:** A dict-type detection header (split? combined? unicode?) that selects the correct layout before reading. Currently we attempt this but the detection itself is fragile.

---

## 3. No write support yet (Phase 2 gap)

X-RAY is complete — we read anything. SCALPEL (write) is in progress but not functional. This means:

- Can't pin objects to static addresses reliably
- Can't mutate in place
- Can't test the core value prop (solve Python's space complexity)
- Can't build the tools that depend on it (PyJx, Nexus, COBALT)

Writing to live memory is fundamentally harder than reading. You need to know:
- Which fields are safe to mutate (data fields vs runtime-metadata fields)
- Which mutations trigger segfaults (corrupting type pointers, refcounts, etc.)
- How to validate state before and after mutation

---

## 4. No safe mutation protocol

Even when SCALPEL works, raw memory mutation is dangerous. There's no:
- Transaction model (make changes → validate → commit/rollback)
- Safety net for common mistakes (writing to freed memory, corrupting type pointers)
- Recovery mechanism when something goes wrong

**What this looks like in practice:** One bad write and the interpreter crashes. No backtrace tells you it was PyProbe. You just lose your session.

**The vision is clear:** surgical transactions with guardrails. The implementation is not.

---

## 5. Version discovery doesn't exist

PyProbe assumes CPython 3.14. It doesn't:
- Detect the current CPython version
- Adjust offsets based on version
- Fall back gracefully for unsupported versions
- Warn users when offsets are likely wrong

This is the root cause of problems 1 and 2. Fix version discovery and both get easier.

---

## 6. No C extension fallback

Using pure ctypes is elegant — no compilation, no build step — but it has limits:
- Performance overhead from repeated ctype struct overlays
- No way to intercept CPython allocation hooks
- Limited ability to protect against corrupted reads

Some operations (like safe memory mutation) would be more reliable with a small C extension providing the core operations, with ctypes as the user-facing layer.

---

## 7. Cross-runtime thread safety is undefined

If two runtimes (Python + Java via PyJx) hold pointers to the same memory:
- Concurrent writes corrupt data
- GC on one side invalidates pointers on the other
- No lock protocol exists yet

This is a future problem (PyJx doesn't work yet) but designing for it now would save pain.

---

## Summary

| Problem | Impact | Effort to Fix | Priority |
|---------|--------|---------------|----------|
| Hardcoded offsets | Breaks on non-3.14 | High | 1 |
| Dict reads unreliable | Wrong data returned | Medium | 1 |
| No write support | Core promise unfulfilled | High | 2 |
| No safe mutation protocol | Dangerous to use | High | 2 |
| No version discovery | Root cause of 1, 2 | Medium | 1 |
| No C extension | Performance ceiling | Low | 3 |
| Thread safety undefined | Future risk | Low | 3 |

**Priority 1 = blocks correctness.** Priority 2 = blocks usefulness. Priority 3 = blocks scaling.
