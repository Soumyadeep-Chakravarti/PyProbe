# Changelog

## Unreleased

### Changed
- Tightened probe typing across the memory-audit tests to satisfy strict Pylance checks.
- Added explicit pointer guards around `ctypes` reads so nullable addresses are rejected before memory access.
- Cleaned up the extended type tests with explicit helper annotations for nested functions, lambdas, closures, and generators.

### Fixed
- Removed unused imports and other strict-type issues from the diagnostic probe scripts.
- Stabilized the stride-discovery and live-address probes by normalizing `int | None` pointer reads before offset math.
