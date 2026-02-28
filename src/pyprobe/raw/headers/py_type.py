import ctypes

class PyTypeObject(ctypes.Structure):
    """The 'Class' definition in memory"""
    _fields_ = [
        ("ob_refcnt", ctypes.c_ssize_t),
        ("ob_type_ptr", ctypes.c_void_p),
        ("ob_size", ctypes.c_ssize_t),
        ("tp_name", ctypes.c_char_p), 
        # ... hundreds of other fields exist here, but we only need the name
    ]
