import ctypes

class FloatLens(ctypes.Structure):
    """Surgical view of the Float's value data (starts after PyObject_HEAD)."""
    _fields_ = [
        ("ob_fval", ctypes.c_double),
    ]
