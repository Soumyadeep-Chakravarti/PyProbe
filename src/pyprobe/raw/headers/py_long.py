import ctypes

class PyLongObject(ctypes.Structure):
    """Mirror of the CPython 3.12+ PyLongObject structure."""
    _fields_ = [
        ("ob_refcnt", ctypes.c_ssize_t),
        ("ob_type_ptr", ctypes.c_void_p),
        ("lv_tag", ctypes.c_size_t),
        ("ob_digit", ctypes.c_uint32 * 1) # Flexible array
    ]
