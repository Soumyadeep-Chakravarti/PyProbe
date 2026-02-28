# src/pyprobe/memory.py
import ctypes

def update_float(pointer, new_value):
    """Surgery: Overwrite a float in-place."""
    # Ensure it's a float
    c_val = ctypes.c_double(float(new_value))
    # Move the 8 bytes of the double into the payload address
    ctypes.memmove(pointer.payload_addr, ctypes.addressof(c_val), 8)
