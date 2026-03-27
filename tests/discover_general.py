import ctypes

d = {1: "a", 2: "b"} # Int keys
addr = id(d)
keys_addr = ctypes.c_void_p.from_address(addr + 32).value
metadata = ctypes.string_at(keys_addr, 32)
start = 32 + (1 << metadata[9])
entries = ctypes.string_at(keys_addr + start, 128)

print(f"Indices log2_total: {metadata[9]}")
print(f"Pointers: {hex(ctypes.c_void_p.from_address(keys_addr + start).value or 0)}")
print(f"Pointers+8: {hex(ctypes.c_void_p.from_address(keys_addr + start + 8).value or 0)}")
print(f"Pointers+16: {hex(ctypes.c_void_p.from_address(keys_addr + start + 16).value or 0)}")
print(f"Pointers+24: {hex(ctypes.c_void_p.from_address(keys_addr + start + 24).value or 0)}")

print(f"ID 1: {hex(id(1))}")
print(f"ID 'a': {hex(id('a'))}")
