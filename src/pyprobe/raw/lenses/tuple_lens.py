import ctypes

class TupleLens(ctypes.Structure):
    """Surgical view of PyTupleObject fields (starts after PyObject_HEAD)."""
    _fields_ = [
        ("ob_size", ctypes.c_ssize_t),
        ("ob_item", ctypes.c_void_p * 1),
    ]
