import ctypes

class PyASCIIObject(ctypes.Structure):
    _fields_ = [
        ("ob_refcnt", ctypes.c_ssize_t),
        ("ob_type_ptr", ctypes.c_void_p),
        ("length", ctypes.c_ssize_t),
        ("hash", ctypes.c_ssize_t),
        ("interned", ctypes.c_uint32, 2),
        ("kind", ctypes.c_uint32, 3),
        ("compact", ctypes.c_uint32, 1),
        ("ascii", ctypes.c_uint32, 1),
        ("ready", ctypes.c_uint32, 1),
        ("padding", ctypes.c_uint32, 24),
    ]

class PyCompactUnicodeObject(PyASCIIObject):
    _fields_ = [
        ("utf8_length", ctypes.c_ssize_t),
        ("utf8_ptr", ctypes.c_void_p),
    ]
