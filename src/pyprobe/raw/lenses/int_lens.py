import ctypes

class IntLens(ctypes.Structure):
    _fields_ = [
        ("ob_size", ctypes.c_ssize_t), 
        ("ob_digit", ctypes.c_uint32 * 2)
    ]
