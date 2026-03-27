import ctypes

class StringLens(ctypes.Structure):
    """Surgical view of PyASCIIObject fields (starts after PyObject_HEAD)."""
    _fields_ = [
        ("length", ctypes.c_ssize_t),
        ("hash", ctypes.c_ssize_t),
        ("interned", ctypes.c_uint32, 2),
        ("kind", ctypes.c_uint32, 3),
        ("compact", ctypes.c_uint32, 1),
        ("ascii", ctypes.c_uint32, 1),
        ("ready", ctypes.c_uint32, 1),
        ("padding", ctypes.c_uint32, 24),
    ]

class CompactUnicodeLens(StringLens):
    """Surgical view of PyCompactUnicodeObject fields (starts after PyASCIIObject)."""
    _fields_ = [
        ("utf8_length", ctypes.c_ssize_t),
        ("utf8_ptr", ctypes.c_void_p),
    ]
