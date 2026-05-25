# Discussion Notes — 2026-05-14

**Up**: [PyProbe](../PyProbe.md)

## Refcount hijack for pinning
- Set `ob_refcnt` to sentinel value → GC never frees the object
- Pin = move to manual allocation pool. User owns it now.
- To unpin: `free()` directly. No shadow registry needed (but add one for debug/dev mode)
- `Pointer` should hold: address, original_refcount, target object reference, type_name, pinned_at timestamp
- Keeping `target` alive prevents GC from collecting the name — two layers of safety

## Thread safety
- Cross-runtime concurrent access creates race conditions
- Fix: per-object read-write lock in PyProbe
- All bridges inherit it for free
- Only applies to pinned objects, unpinned objects unaffected
- Implement in PyProbe so PyJx and everything above gets it without extra work

## Cross-language without porting
- CPython is C. C struct layouts are the bridge.
- Publish struct headers → every language reads Python memory via its own C FFI
- No SDK per language needed. PyProbe does the Python side (pin + give address + struct layout). Foreign language does the rest.

## Key realization
- X-RAY is prerequisite, not the product. SCALPEL (write) is the actual value.
- Pinning without mutation is a fossil. Pinning + write is the solution to Python's space complexity.

## Phase priorities (reaffirmed)
1. Fix generalization (runtime probing, reliable dicts)
2. SCALPEL (safe mutation)
3. Thread safety
4. Cross-language bridges (PyJx first)
