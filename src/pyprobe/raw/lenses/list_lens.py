import ctypes

class ListLens(ctypes.Structure):
    _fields_ = [
        ("ob_size", ctypes.c_ssize_t), 
        ("ob_item", ctypes.POINTER(ctypes.c_void_p)), 
        ("allocated", ctypes.c_ssize_t)
    ]
