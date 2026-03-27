import ctypes
import os

def get_keys_header(d):
    keys_addr = ctypes.c_void_p.from_address(id(d) + 32).value
    return ctypes.string_at(keys_addr, 32)

def audit_dicts():
    sizes = [1, 10, 100, 1000]
    for s in sizes:
        d = {i: i for i in range(s)}
        header = get_keys_header(d)
        print(f"Size {s:4} | Header: {header.hex(' ')}")

if __name__ == "__main__":
    audit_dicts()
