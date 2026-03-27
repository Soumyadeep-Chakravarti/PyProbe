import ctypes
t = (1, 2)
addr = id(t)
size = ctypes.c_ssize_t.from_address(addr + 16).value
print(f"Tuple Size: {size}")
raw = ctypes.string_at(addr, 64)
print(f"Tuple Raw: {raw.hex(' ')}")
p1 = ctypes.c_void_p.from_address(addr + 24).value
p2 = ctypes.c_void_p.from_address(addr + 32).value
print(f"Item Pointers: {hex(p1 or 0)}, {hex(p2 or 0)}")
print(f"ID 1: {hex(id(1))}, ID 2: {hex(id(2))}")
