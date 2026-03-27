import ctypes
d2 = {1: "a", 2.5: "b", (1,2): "c"}
addr = id(d2)
keys_addr = ctypes.c_void_p.from_address(addr + 32).value
nentries = ctypes.c_ssize_t.from_address(keys_addr + 24).value
print(f"nentries: {nentries}")
print(f"usable: {ctypes.c_ssize_t.from_address(keys_addr + 16).value}")
