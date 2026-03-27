"""Collections.py ."""

import ctypes


class PyBytesObject(ctypes.Structure):
    """Mirror of PyBytesObject (VAR_HEAD + hash + inline data)."""

    _fields_ = [
        ("ob_refcnt", ctypes.c_ssize_t),
        ("ob_type_ptr", ctypes.c_void_p),
        ("ob_size", ctypes.c_ssize_t),
        ("ob_shash", ctypes.c_ssize_t),
        ("ob_sval", ctypes.c_char * 1)  # Start of data
    ]


class PySetEntry(ctypes.Structure):
    """Set entry."""

    _fields_ = [
        ("key", ctypes.c_void_p),
        ("hash", ctypes.c_ssize_t),
    ]


class PySetObject(ctypes.Structure):
    """Mirror of PySetObject (Header + fill/used/mask + table pointer)."""

    _fields_ = [
        ("ob_refcnt", ctypes.c_ssize_t),
        ("ob_type_ptr", ctypes.c_void_p),
        ("fill", ctypes.c_ssize_t),
        ("used", ctypes.c_ssize_t),
        ("mask", ctypes.c_ssize_t),
        ("table", ctypes.POINTER(PySetEntry)),
        ("hash", ctypes.c_ssize_t),
        ("finger", ctypes.c_ssize_t),
        ("table_initial", PySetEntry * 8),  # PySet_MINSIZE = 8
    ]
