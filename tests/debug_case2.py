import ctypes
import os

d2 = {1: "a", 2.5: "b", (1,2): "c"} # General Keys
addr = id(d2)
keys_addr = ctypes.c_void_p.from_address(addr + 32).value
metadata = ctypes.string_at(keys_addr, 32)
print(f"Metadata bytes 8-11: {metadata[8:12].hex(' ')}")
# Also audit entries
start = 32 + (1 << metadata[9])
print(f"Start of entries: {hex(start)}")
raw = ctypes.string_at(keys_addr + start, 128)
print(f"Raw entries sample: {raw.hex(' ')}")
