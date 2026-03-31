"""CPython header structure definitions.

This module provides ctypes-based mirrors of CPython's internal C structures,
allowing direct memory access to Python object headers.
"""

from .py_object import PyObjectHeader
from .py_type import PyTypeObject
from .py_long import PyLongObject
from .py_float import PyFloatObject
from .py_unicode import PyASCIIObject, PyCompactUnicodeObject
from .py_list import PyListObject
from .py_tuple import PyTupleObject
from .py_dict import PyDictObject, DictKeysObject
from .py_collections import PyBytesObject, PySetObject, PySetEntry

__all__ = [
    "PyObjectHeader",
    "PyTypeObject",
    "PyLongObject",
    "PyFloatObject",
    "PyASCIIObject",
    "PyCompactUnicodeObject",
    "PyListObject",
    "PyTupleObject",
    "PyDictObject",
    "DictKeysObject",
    "PyBytesObject",
    "PySetObject",
    "PySetEntry",
]
