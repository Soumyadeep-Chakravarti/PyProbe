import ctypes

d = {"a": 1}
d_addr = id(d)
keys_addr = ctypes.c_void_p.from_address(d_addr + 32).value
data = ctypes.string_at(keys_addr, 32)

print(f"Header: {data.hex(' ')}")
for i, b in enumerate(data):
    print(f"[{i:02d}] : {b:02x}")
