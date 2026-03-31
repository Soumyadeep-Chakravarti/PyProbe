"""Lens views for Python object bodies.

Lenses provide body-only views of Python objects, skipping the 16-byte
PyObject_HEAD. This enables clean access to type-specific data.
"""

from .int_lens import IntLens
from .float_lens import FloatLens
from .str_lens import StringLens, CompactUnicodeLens
from .list_lens import ListLens
from .tuple_lens import TupleLens
from .dict_lens import DictLens, DictKeysLens
from .set_lens import SetLens
from .bytes_lens import BytesLens

__all__ = [
    "IntLens",
    "FloatLens",
    "StringLens",
    "CompactUnicodeLens",
    "ListLens",
    "TupleLens",
    "DictLens",
    "DictKeysLens",
    "SetLens",
    "BytesLens",
]
