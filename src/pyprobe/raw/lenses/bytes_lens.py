import ctypes

class BytesLens(ctypes.Structure):
    """Surgical view of PyBytesObject (VAR_HEAD fields)."""
    _fields_ = [
        ("ob_size", ctypes.c_ssize_t),
        ("ob_shash", ctypes.c_ssize_t),
        ("ob_sval", ctypes.c_char * 1)
    ]
