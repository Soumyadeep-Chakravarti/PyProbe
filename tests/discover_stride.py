import ctypes

d = {"a": 1, "b": 2} # 2 entries
addr = id(d)
keys_addr = ctypes.c_void_p.from_address(addr + 32).value
metadata = ctypes.string_at(keys_addr, 32)
# log2_indices_total = metadata[9]
start = 32 + (1 << metadata[9])
entries = ctypes.string_at(keys_addr + start, 64)

print(f"Indices log2_total: {metadata[9]}")
print(f"Entries Raw: {entries.hex(' ')}")
# We can find the second key to determine stride
# First key is at start+8 (if stride 24) or start+0 (if stride 16)
p1 = ctypes.c_void_p.from_address(keys_addr + start).value
p2 = ctypes.c_void_p.from_address(keys_addr + start + 8).value
p3 = ctypes.c_void_p.from_address(keys_addr + start + 16).value
p4 = ctypes.c_void_p.from_address(keys_addr + start + 24).value

print(f"Pointers: {hex(p1 or 0)}, {hex(p2 or 0)}, {hex(p3 or 0)}, {hex(p4 or 0)}")
# Key 'a' should be one of these
print(f"ID 'a': {hex(id('a'))}")
print(f"ID 'b': {hex(id('b'))}")
