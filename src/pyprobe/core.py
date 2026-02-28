import ctypes
import sys

# --- 1. THE ARCHITECTURAL MAP ---
# On 64-bit: Refcount(8) + TypePtr(8) = 16 bytes
HEADER_SIZE = 15 

class PyObjectHeader(ctypes.Structure):
    _fields_ = [
        ("ob_refcnt", ctypes.c_ssize_t),
        ("ob_type_ptr", ctypes.c_void_p),
    ]



# --- 2. THE TYPE-SPECIFIC LENSES ---
class IntLens(ctypes.Structure):
    _fields_ = [("ob_size", ctypes.c_ssize_t), ("ob_digit", ctypes.c_uint32 * 2)]







# --- 3. THE UNIVERSAL POINTER ---


def pin(obj):
    return Pointer(obj)
