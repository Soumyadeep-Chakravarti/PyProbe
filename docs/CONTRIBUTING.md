# Contributing to PyProbe

Welcome to PyProbe! This document will help you get set up and productive quickly.

---

## Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone <repo-url>
cd PyProbe

# Create virtual environment (using uv, recommended)
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Or using standard venv
python -m venv .venv
source .venv/bin/activate

# Install in development mode
uv pip install -e .
# Or: pip install -e .
```

### 2. Verify Installation

```bash
# Run the tests
python tests/run_all.py

# Or with pytest
pytest tests/

# Try the interactive REPL
python tools/explorer_repl.py
```

### 3. Try It Out

```python
import pyprobe

# Pin an object and examine it
x = [1, 2, 3]
ptr = pyprobe.pin(x)
ptr.examine()

# Extract data from memory
data = ptr.xray()
print(data)  # [1, 2, 3]
```

---

## Project Structure

```
PyProbe/
├── src/pyprobe/           # Main source code
│   ├── __init__.py        # Public API
│   ├── core/              # Core functionality
│   │   └── pointer/
│   │       └── engine.py  # The Pointer class (start here!)
│   └── raw/               # CPython struct definitions
│       ├── headers/       # Full object headers
│       └── lenses/        # Body-only views
├── tests/                 # Test suite
├── tools/                 # Debugging utilities
├── docs/                  # Documentation (you are here)
├── examples/              # Usage examples
└── main.py                # Demo script
```

---

## Documentation Guide

Read these in order:

| Order | Document | What You'll Learn |
|-------|----------|-------------------|
| 1 | [README](../README.md) | Project overview |
| 2 | [ROADMAP](./ROADMAP.md) | Where we're going |
| 3 | [ARCHITECTURE](./ARCHITECTURE.md) | How the code is organized |
| 4 | [CPYTHON_MEMORY](./CPYTHON_MEMORY.md) | CPython internals reference |
| 5 | [SAFETY_MODEL](./SAFETY_MODEL.md) | Critical safety rules |

---

## Development Workflow

### Before You Code

1. **Read the relevant docs** - Especially ARCHITECTURE and CPYTHON_MEMORY
2. **Check existing issues** - Someone might already be working on it
3. **Create an issue** - For significant changes, discuss first

### Making Changes

```bash
# Create a branch
git checkout -b feature/your-feature-name

# Make your changes
# ... edit files ...

# Run tests
python tests/run_all.py

# Commit with a clear message
git commit -m "Add: brief description of what you added"
# or "Fix:", "Update:", "Refactor:", etc.

# Push and create PR
git push origin feature/your-feature-name
```

### Commit Message Format

```
Type: Brief description (max 50 chars)

Longer description if needed. Explain WHY, not just WHAT.
Reference issues with #123.
```

Types:
- `Add:` - New feature
- `Fix:` - Bug fix
- `Update:` - Enhancement to existing feature
- `Refactor:` - Code restructure without behavior change
- `Docs:` - Documentation only
- `Test:` - Test only

---

## Code Style

### Python

- Follow PEP 8
- Use type hints for public functions
- Maximum line length: 100 characters
- Use docstrings for classes and public methods

```python
def example_function(addr: int, depth: int = 0) -> Optional[str]:
    """
    Brief description of what the function does.

    Args:
        addr: Memory address to inspect
        depth: Current recursion depth

    Returns:
        Extracted string value, or None if invalid
    """
    pass
```

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Classes | PascalCase | `Pointer`, `DictLens` |
| Functions/Methods | snake_case | `pull_data_from_address` |
| Private | Leading underscore | `_extract_int` |
| Constants | UPPER_SNAKE | `HEADER_SIZE` |
| ctypes structs | PascalCase | `PyObjectHeader` |

### File Organization

- One concept per file (usually)
- Keep files under 500 lines if possible
- Related functionality in the same directory

---

## Testing

### Running Tests

```bash
# All tests
python tests/run_all.py

# Specific test file
python -m pytest tests/test_primitives.py

# Specific test
python -m pytest tests/test_primitives.py::TestIntegers::test_small_int

# With verbose output
python -m pytest -v tests/
```

### Writing Tests

```python
import unittest
import pyprobe

class TestYourFeature(unittest.TestCase):
    def test_basic_case(self):
        """Test description."""
        # Setup
        obj = [1, 2, 3]
        ptr = pyprobe.pin(obj)

        # Action
        result = ptr.xray()

        # Assert
        self.assertEqual(result, [1, 2, 3])

    def test_edge_case(self):
        """Test empty input."""
        obj = []
        ptr = pyprobe.pin(obj)
        result = ptr.xray()
        self.assertEqual(result, [])

    def test_error_handling(self):
        """Test invalid input."""
        ptr = pyprobe.pin(1)
        result = ptr.pull_data_from_address(0)  # NULL
        self.assertEqual(result, "NULL")
```

### Test Categories

| File | What to Test |
|------|--------------|
| `test_primitives.py` | int, float, str, bytes |
| `test_collections.py` | list, tuple, dict, set |
| `test_graphs.py` | Cycles, deep nesting |
| `test_safety.py` | Invalid addresses, corruption |
| `test_mutations.py` | (Future) Write operations |

---

## Adding New Features

### Adding a New Type Extractor

1. **Create a lens** in `src/pyprobe/raw/lenses/`:

```python
# src/pyprobe/raw/lenses/your_lens.py
import ctypes

class YourLens(ctypes.Structure):
    """Lens for YourType - starts at offset +16."""
    _fields_ = [
        ("field1", ctypes.c_ssize_t),
        ("field2", ctypes.c_void_p),
        # ... type-specific fields
    ]
```

2. **Add extractor method** in `src/pyprobe/core/pointer/engine.py`:

```python
def _extract_yourtype(self, addr: int) -> Any:
    """Extract YourType from memory address."""
    lens = YourLens.from_address(addr + 16)
    # ... extraction logic
    return result
```

3. **Register in dispatcher**:

```python
# In Pointer.__init__
self._extractors = {
    # ... existing extractors
    'yourtype': self._extract_yourtype,
}
```

4. **Add tests** in `tests/test_*.py`:

```python
def test_yourtype_basic(self):
    obj = YourType(...)
    ptr = pyprobe.pin(obj)
    result = ptr.xray()
    self.assertEqual(result, expected)
```

5. **Update documentation** if needed

### Adding Mutation Support (Phase 2)

**IMPORTANT**: Read [SAFETY_MODEL.md](./SAFETY_MODEL.md) first!

1. **Add safety check**:

```python
def _can_mutate_yourtype(self, addr: int) -> Tuple[bool, str]:
    """Check if YourType at addr can be safely mutated."""
    # Check refcount
    refcnt = ctypes.c_ssize_t.from_address(addr).value
    if refcnt > 2:  # Accounting for our reference
        return False, "Object is shared"
    
    # Type-specific checks
    # ...
    
    return True, "Safe"
```

2. **Add mutation method**:

```python
def mutate_yourtype(self, new_value) -> None:
    """Mutate YourType in place."""
    safe, reason = self._can_mutate_yourtype(self.address)
    if not safe:
        raise ValueError(f"Cannot mutate: {reason}")
    
    # Perform mutation
    # ...
```

3. **Add safety tests**:

```python
def test_rejects_shared_object(self):
    a = YourType(...)
    b = a  # Now shared
    ptr = pyprobe.pin(a)
    with self.assertRaises(ValueError):
        ptr.mutate_yourtype(new_value)
```

---

## Debugging Tips

### Segmentation Faults

If you get a segfault:

1. **Check address validity** - Is it aligned? Is it > 0x1000?
2. **Check type** - Are you applying the right lens?
3. **Check offsets** - Are you reading from the right location?
4. **Use the REPL** - `tools/explorer_repl.py` for interactive debugging

### Common Issues

| Problem | Likely Cause | Solution |
|---------|--------------|----------|
| Segfault on read | Invalid address | Check address validation |
| Wrong value | Wrong offset | Verify against CPYTHON_MEMORY.md |
| Type mismatch | Version difference | Check Python version |
| "Corrupt Type" | Bad type pointer | Object may be deallocated |

### Useful Debugging Code

```python
import ctypes

def dump_memory(addr, size=64):
    """Hex dump of memory at address."""
    data = ctypes.string_at(addr, size)
    for i in range(0, len(data), 16):
        hex_part = ' '.join(f'{b:02x}' for b in data[i:i+16])
        print(f'{addr+i:016x}: {hex_part}')

# Usage
dump_memory(id(my_object))
```

---

## Getting Help

1. **Check the docs** - Answer might be there
2. **Search existing issues** - Someone may have asked
3. **Ask the team** - Create an issue or reach out
4. **Read the source** - engine.py is well-commented

---

## Code Review Checklist

When reviewing PRs, check:

- [ ] **Tests pass** - All existing tests still pass
- [ ] **New tests added** - For new functionality
- [ ] **Safety considered** - For any mutation code
- [ ] **Documentation updated** - If API changed
- [ ] **Code style** - Follows conventions
- [ ] **No magic numbers** - Use constants
- [ ] **Error handling** - Graceful failure
- [ ] **Type hints** - On public functions

---

## Recognition

Contributors will be acknowledged in:

- The README
- Release notes
- Paper acknowledgments (for significant contributions)

---

## Questions?

- Check the documentation first
- Search existing issues
- Create a new issue if still stuck

Welcome to the team!
