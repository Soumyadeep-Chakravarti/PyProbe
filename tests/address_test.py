import pyprobe
from pyprobe.core.Scalpel import (
    mutate_float,
    mutate_int,
    safe_list_swap,
    safe_dict_value_swap,
    mutate_bytes,
    mutate_str
)

print("=" * 55)
print("PHASE 1 + PHASE 2 COMBINED TEST")
print("Address same rehna chahiye after mutation!")
print("=" * 55)

# ── Float Test ──────────────────────────────────────────
print("\n[ FLOAT ]")
f = float("100." + "5")
ptr = pyprobe.pin(f)

print("  Before mutation:")
print(f"    Address : {hex(id(f))}")
print(f"    Value   : {ptr.xray()}")

mutate_float(f, 999.99)

print("  After mutation:")
print(f"    Address : {hex(id(f))}")   # same hona chahiye
print(f"    Value   : {ptr.xray()}")     # 999.99 hona chahiye
print(f"    Match   : {hex(id(f)) == hex(ptr.address)}")

# ── Int Test ────────────────────────────────────────────
print("\n[ INT ]")
big = int("1" + "0" * 18)
ptr = pyprobe.pin(big)

print(f"  Before mutation:")
print(f"    Address : {hex(id(big))}")
print(f"    Value   : {ptr.xray()}")

mutate_int(big, 42)

print(f"  After mutation:")
print(f"    Address : {hex(id(big))}")   # same hona chahiye
print(f"    Value   : {ptr.xray()}")     # 42 hona chahiye
print(f"    Match   : {hex(id(big)) == hex(ptr.address)}")

# ── List Test ───────────────────────────────────────────
print("\n[ LIST ]")
lst = list((10, 20, 30))
ptr = pyprobe.pin(lst)

print(f"  Before mutation:")
print(f"    Address : {hex(id(lst))}")
print(f"    Value   : {ptr.xray()}")

safe_list_swap(lst, 1, "MUTATED")

print(f"  After mutation:")
print(f"    Address : {hex(id(lst))}")   # same hona chahiye
print(f"    Value   : {ptr.xray()}")     # [10, 'MUTATED', 30]
print(f"    Match   : {hex(id(lst)) == hex(ptr.address)}")

# ── Dict Test ───────────────────────────────────────────
print("\n[ DICT ]")
d = dict(status="secure", version=1)
ptr = pyprobe.pin(d)

print(f"  Before mutation:")
print(f"    Address : {hex(id(d))}")
print(f"    Value   : {ptr.xray()}")

safe_dict_value_swap(d, "status", "mutated")

print(f"  After mutation:")
print(f"    Address : {hex(id(d))}")    # same hona chahiye
print(f"    Value   : {ptr.xray()}")    # status: mutated
print(f"    Match   : {hex(id(d)) == hex(ptr.address)}")

# ── Bytes Test ──────────────────────────────────────────
print("\n[ BYTES ]")
b = bytes(bytearray([65, 66, 67, 68]))
ptr = pyprobe.pin(b)

print(f"  Before mutation:")
print(f"    Address : {hex(id(b))}")
print(f"    Value   : {ptr.xray()}")

mutate_bytes(b, b"WXYZ")

print(f"  After mutation:")
print(f"    Address : {hex(id(b))}")    # same hona chahiye
print(f"    Value   : {ptr.xray()}")    # b'WXYZ' hona chahiye
print(f"    Match   : {hex(id(b)) == hex(ptr.address)}")

# ── String Test ─────────────────────────────────────────
print("\n[ STRING ]")
s = "".join(["1", "2", "3", "4"])
ptr = pyprobe.pin(s)

print(f"  Before mutation:")
print(f"    Address : {hex(id(s))}")
print(f"    Value   : {ptr.xray()}")

mutate_str(s, "5678")

print(f"  After mutation:")
print(f"    Address : {hex(id(s))}")    # same hona chahiye
print(f"    Value   : {ptr.xray()}")    # '5678' hona chahiye
print(f"    Match   : {hex(id(s)) == hex(ptr.address)}")

# ── Summary ─────────────────────────────────────────────
print("\n" + "=" * 55)
print("=" * 55)