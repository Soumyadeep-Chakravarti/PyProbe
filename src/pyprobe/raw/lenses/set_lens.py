import ctypes
from pyprobe.raw.headers.py_collections import PySetEntry

class SetLens(ctypes.Structure):
    """Surgical view of PySetObject (after ob_type_ptr)."""
    _fields_ = [
        ("fill", ctypes.c_ssize_t),
        ("used", ctypes.c_ssize_t),
        ("mask", ctypes.c_ssize_t),
        ("table", ctypes.POINTER(PySetEntry)),
        ("hash", ctypes.c_ssize_t),
        ("finger", ctypes.c_ssize_t),
        ("table_initial", PySetEntry * 8),
    ]
