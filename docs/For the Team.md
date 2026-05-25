# PyProbe — For the Team

**Up**: [PyProbe](../PyProbe.md)

## What it is

A Python library that lets you read and write Python object memory directly. Like having a debugger that lives inside your code.

## The problem we're solving

Every time you do `x = x + 1` in Python, Python:
1. Grabs new memory
2. Writes the result there
3. Throws away the old memory

For one line of code? Fine. For an ML model updating 7 billion parameters? That's 7 billion memory allocations you didn't need. You just wanted to change a number in place. Python makes you copy everything instead.

Other languages (C, Rust, Java) don't have this problem because they let you mutate in place. Python prioritizes developer ease over memory efficiency. We're fixing that.

## How PyProbe helps

```python
from pyprobe import pin

# Look inside any Python object at the C level
info = pin(some_object).examine()

# Extract the actual value from memory
value = pin(some_object).xray()

# (Coming soon) Mutate in-place without re-allocation
pin(some_object).write(field, new_value)
```

No C extensions. No compilation. Pure Python that reads memory.

## The bigger vision

If objects stay at the same memory address (they don't move around), other languages can hold pointers to them:

1. **Pin** a Python object so it never moves
2. **Hand its address** to Java, Rust, or C
3. **Both runtimes share the same memory** — no copying data between them

This means:
- Pass Python functions to Java by reference
- Mutate Python lists from Rust, zero copy
- Share a dict between Python and Go without serialization

## What's done

- **X-RAY**: Read any Python object from memory. Works for 50+ types.

## What's in progress

- **SCALPEL**: Write to Python memory in-place (safe mutation without crashes)
- **Generalization**: Make it work across CPython versions, not just 3.14
- **Thread safety**: Handle multiple runtimes accessing the same memory

## Plain English questions? Ask.

The code lives at `~/projects/PyProbe` or on GitHub. Come find me if anything's confusing.
