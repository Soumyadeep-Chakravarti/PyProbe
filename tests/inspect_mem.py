import ctypes

# Look at dict memory structure directly
d: dict[str, int] = {"a": 1}
d_addr = id(d)
# So ma_keys is at +32.
keys_addr: int | None = ctypes.c_void_p.from_address(d_addr + 32).value
if keys_addr is None:
	raise RuntimeError("Could not locate dict keys address.")

print(f"Dict Address: {hex(d_addr)}")
print(f"Keys Address: {hex(keys_addr)}")

# Heuristic scan of the first few bytes of keys_addr
data = ctypes.string_at(keys_addr, 64)
print(f"Keys Raw: {data.hex(' ')}")

# We expect:
# refcnt (8)
# log2_size (1) -> 3
# log2_indices (1) -> 0
# kind (1) -> 1 (Unicode)
# version_header (1) -> ?
# version (4) -> ?
# usable (8) -> 4
# nentries (8) -> 1
# indices (8 bytes) -> [...]
# entries (16 bytes) -> [...]

# In 08 00 00 00 00 00 00 00 (refcnt=8)
#    03 00 01 10 (size=3, ind=0, kind=1, ver_h=10?)
#    ...
