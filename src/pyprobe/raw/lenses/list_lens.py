import ctypes

class ListLens(ctypes.Structure):
    """Surgical view of PyListObject fields (starts after PyObject_HEAD)."""
    _fields_ = [
        ("ob_size", ctypes.c_ssize_t),
        ("ob_item", ctypes.POINTER(ctypes.c_void_p)),
        ("allocated", ctypes.c_ssize_t),
    ]
