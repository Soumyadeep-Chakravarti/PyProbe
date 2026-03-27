import ctypes
import sys

# Look at dict memory structure directly
d = {"a": 1}
d_addr = id(d)
ma_keys_ptr = ctypes.c_void_p.from_address(d_addr + 48).value # 16 + 8 + 8 + 8 + 8?
# Let's verify ma_keys address
# CPython 3.12 dict:
# refcnt (8)
# type_ptr (8)
# ma_used (8)
# ma_version_tag (8)
# ma_keys (8)
# ma_values (8)

# So ma_keys is at +32.
keys_addr = ctypes.c_void_p.from_address(d_addr + 32).value

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
