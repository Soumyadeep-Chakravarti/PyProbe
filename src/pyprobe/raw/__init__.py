"""Raw memory access utilities.

This package provides low-level ctypes structures for accessing
CPython object memory layouts:

- headers: Full CPython struct mirrors including PyObject_HEAD
- lenses: Body-only views that skip the 16-byte header
"""

from . import headers
from . import lenses

__all__ = ["headers", "lenses"]
