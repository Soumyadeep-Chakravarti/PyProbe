import ctypes

class FloatLens(ctypes.Structure):
    _fields_ = [("ob_fval", ctypes.c_double)]
