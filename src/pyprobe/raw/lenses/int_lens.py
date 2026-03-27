import ctypes

class IntLens(ctypes.Structure):
    """Surgical view of the Integer's value data (starts after PyObject_HEAD)."""
    _fields_ = [
        ("lv_tag", ctypes.c_size_t),
        ("ob_digit", ctypes.c_uint32 * 1) # Flexible array
    ]
