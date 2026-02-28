import ctypes

class StringLens(ctypes.Structure):
    _fields_ = [
        ("length", ctypes.c_ssize_t),
        ("hash", ctypes.c_ssize_t),
        ("state", ctypes.c_uint32), # Flags for ASCII/Compact/etc
        ("wstr", ctypes.c_void_p)
    ]
