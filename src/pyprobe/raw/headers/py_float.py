import ctypes

class PyFloatObject(ctypes.Structure):
    _fields_ = [
        ("ob_refcnt", ctypes.c_ssize_t),
        ("ob_type_ptr", ctypes.c_void_p),
        ("ob_fval", ctypes.c_double),
    ]
