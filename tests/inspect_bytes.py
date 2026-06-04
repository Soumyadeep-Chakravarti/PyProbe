import ctypes

d: dict[str, int] = {"a": 1}
d_addr = id(d)
keys_addr: int | None = ctypes.c_void_p.from_address(d_addr + 32).value
if keys_addr is None:
    raise RuntimeError("Could not locate dict keys address.")
data = ctypes.string_at(keys_addr, 32)

print(f"Header: {data.hex(' ')}")
for i, b in enumerate(data):
    print(f"[{i:02d}] : {b:02x}")
