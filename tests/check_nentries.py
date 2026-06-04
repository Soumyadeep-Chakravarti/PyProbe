import ctypes
d2: dict[object, str] = {1: "a", 2.5: "b", (1,2): "c"}
addr = id(d2)
keys_addr: int | None = ctypes.c_void_p.from_address(addr + 32).value
if keys_addr is None:
	raise RuntimeError("Could not locate dict keys address.")
nentries = ctypes.c_ssize_t.from_address(keys_addr + 24).value
print(f"nentries: {nentries}")
print(f"usable: {ctypes.c_ssize_t.from_address(keys_addr + 16).value}")
