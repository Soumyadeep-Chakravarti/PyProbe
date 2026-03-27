import ctypes
x = 1
addr = id(x)
print(f"Tag: {hex(ctypes.c_size_t.from_address(addr + 24).value)}")
print(f"Size: {ctypes.c_size_t.from_address(addr + 24).value >> 3}")
