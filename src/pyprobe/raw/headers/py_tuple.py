import ctypes

class PyTupleObject(ctypes.Structure):
    _fields_ = [
        ("ob_refcnt", ctypes.c_ssize_t),
        ("ob_type_ptr", ctypes.c_void_p),
        ("ob_size", ctypes.c_ssize_t),
        ("ob_item", ctypes.c_void_p * 1), # Variable sized inline array
    ]
