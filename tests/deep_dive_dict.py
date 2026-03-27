import sys
import os
import ctypes
sys.path.insert(0, os.path.abspath("src"))
from pyprobe.core.pointer.engine import Pointer

d1 = {"a": 1, "b": 2}
p = Pointer(d1)
# Inspect ma_keys metadata
keys_addr = p.lens.ma_keys
metadata = ctypes.string_at(keys_addr, 32)
print(f"Metadata: {metadata.hex(' ')}")
log2_ix = metadata[9]
start = 32 + (1 << log2_ix)
print(f"Entries Start: {hex(start)}")
entries = ctypes.string_at(keys_addr + start, 64)
print(f"Entries: {entries.hex(' ')}")

# Manually read first entry
k1 = ctypes.c_void_p.from_address(keys_addr + start).value
v1 = ctypes.c_void_p.from_address(keys_addr + start + 8).value
print(f"Entry 0: Key={hex(k1)}, Val={hex(v1)}")
print(f"ID 'a'={hex(id('a'))}, ID 1={hex(id(1))}")
