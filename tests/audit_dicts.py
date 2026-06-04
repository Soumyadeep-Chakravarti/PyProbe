import ctypes
from typing import Any


def get_keys_header(d: dict[Any, Any]) -> bytes:
    keys_addr: int | None = ctypes.c_void_p.from_address(id(d) + 32).value
    if keys_addr is None:
        raise RuntimeError("Could not locate dict keys header in memory.")
    return ctypes.string_at(keys_addr, 32)

def audit_dicts():
    sizes = [1, 10, 100, 1000]
    for s in sizes:
        d = {i: i for i in range(s)}
        header = get_keys_header(d)
        print(f"Size {s:4} | Header: {header.hex(' ')}")

if __name__ == "__main__":
    audit_dicts()
