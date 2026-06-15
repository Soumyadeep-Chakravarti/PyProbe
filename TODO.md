# PyProbe TODO List

## Phase 1 Improvements

- [x] Add `explain()` method (human-readable interpretation)
- [x] Add `audit()` method (flag anomalies)
- [x] Add `compare(obj2)` method (diff memory layouts)
- [x] Add `to_json()` / `to_dict()` export
- [x] Add ANSI color support (respect `NO_COLOR`)
- [ ] Add `PYPROBE_QUIET` env var
- [x] Add `PYPROBE_COLOR` env var

## Phase 2

- [x] Implement `transaction()` context manager
- [x] Implement `begin()` / `commit()` / `rollback()`
- [x] Add checksum validation (CRC32)
- [ ] Add copy-on-write tracking
- [x] Add bounds checking
- [x] Add refcount validation
- [x] Block interned string mutation
- [x] Protect small int cache (-5 to 256)
- [x] Respect immortal objects (PEP 683)
- [ ] Add `safe=False` parameter to `pin()`
- [ ] Add `disable_safety()` context manager
- [ ] Add `autocommit(every=N)` decorator
- [ ] Add dry run mode

## Error Handling

- [x] Remove all `sys.exit()` calls from core
- [x] Replace with `PyProbeError` exceptions
- [ ] Add `PyProbeFatalError` class
- [x] Add `PyProbeWarning` class

## Documentation

- [x] Write `README.md`
- [x] Write `ARCHITECTURE.md`
- [x] Write `API.md`
- [x] Write `SAFETY_MODEL.md`
- [x] Write `CONTRIBUTING.md`

## Environment Variables

- [x] Implement `PYPROBE_COLOR`
- [ ] Implement `PYPROBE_QUIET`
- [ ] Implement `PYPROBE_FATAL`
- [ ] Implement `PYPROBE_CHECKSUM`

## Ring Buffer Logger (Phase 3)

- [x] Create `src/pyprobe/core/log.py` — `LogRing` class with SPSC circular ring buffer
  - [x] 256B fixed entries: 8B timestamp + 1B level + 1B module_id + 2B msg_len + 244B message
  - [x] 16-byte header: write_pos + read_pos + capacity + flags
  - [x] Hot path optimizations: `monotonic_ns`, `struct.pack_into` batch write, pre-allocated msg buffer
  - [x] Module-level singleton with `get_ring()`
  - [x] Convenience methods: `debug()`, `info()`, `warn()`, `error()`
  - [x] Read-side methods: `flush()`, `peek()`, `clear()`, `stats()`
  - [x] Format on read, not write (timestamp/level formatting at flush time only)
  - [x] ANSI color support via `PYPROBE_COLOR` / `PYPROBE_COLOR_MODE`
- [x] Replace `print()` in `offset_discovery.py` (18 calls) with `ring.info(0, ...)`
- [x] Replace `print()` in `Scalpel.py` `run_tests()` (15 calls) with `ring.info(2, ...)`
- [x] Replace `print()` in `pointer/engine.py` (23 calls) with `ring.debug(3, ...)`
- [x] Replace `warnings.warn()` in `safety.py` (3 calls) with `ring.warn(1, ...)`
- [x] Replace `warnings.warn()` in `pointer/engine.py` (1 call) with `ring.warn(3, ...)`
- [x] Add per-mutation debug logging to all 6 mutation functions in `Scalpel.py`
- [x] Add transaction commit/rollback logging in `Transaction` class
- [x] Export `get_ring` from `pyprobe.core.__init__` and `pyprobe.__init__`
- [x] Write tests for `LogRing` (write, flush, overflow, peek, clear, stats)

## Cleanup

- [ ] Move Colorama to optional dependency
- [x] Add 64-bit guard
- [x] Document CPython 3.12+ only
