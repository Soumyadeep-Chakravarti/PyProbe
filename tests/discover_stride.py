import ctypes

<<<<<<< HEAD

def require_address(value: int | None, label: str) -> int:
	if value is None:
		raise ValueError(f"{label} is null")
	return value

d = {"a": 1, "b": 2} # 2 entries
addr = id(d)
keys_addr = require_address(ctypes.c_void_p.from_address(addr + 32).value, "keys_addr")
=======
d: dict[str, int] = {"a": 1, "b": 2} # 2 entries
addr = id(d)
keys_addr: int | None = ctypes.c_void_p.from_address(addr + 32).value
if keys_addr is None:
	raise RuntimeError("Could not locate dict keys address.")
>>>>>>> test-ruleset-workflow
metadata = ctypes.string_at(keys_addr, 32)
# log2_indices_total = metadata[9]
start: int = 32 + (1 << metadata[9])
entries = ctypes.string_at(keys_addr + start, 64)

print(f"Indices log2_total: {metadata[9]}")
print(f"Entries Raw: {entries.hex(' ')}")
# We can find the second key to determine stride
# First key is at start+8 (if stride 24) or start+0 (if stride 16)
p1 = require_address(ctypes.c_void_p.from_address(keys_addr + start).value, "p1")
p2 = require_address(ctypes.c_void_p.from_address(keys_addr + start + 8).value, "p2")
p3 = require_address(ctypes.c_void_p.from_address(keys_addr + start + 16).value, "p3")
p4 = require_address(ctypes.c_void_p.from_address(keys_addr + start + 24).value, "p4")

print(f"Pointers: {hex(p1 or 0)}, {hex(p2 or 0)}, {hex(p3 or 0)}, {hex(p4 or 0)}")
# Key 'a' should be one of these
print(f"ID 'a': {hex(id('a'))}")
print(f"ID 'b': {hex(id('b'))}")
