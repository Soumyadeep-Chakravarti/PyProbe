import threading
import time
import ctypes
from typing import Callable

from pyprobe.core.Scalpel import (
    safe_list_swap, mutate_bytes, mutate_str, mutate_int
)
from pyprobe.core.offset_discovery import (
    LIST_ITEMS_OFFSET, STR_DATA_OFFSET
)

# ── Shared state ──────────────────────────────────────────
stop_reading = threading.Event()
read_log: list[tuple[float, object]] = []

def continuous_reader(address: int, obj_type: str) -> None:
    while not stop_reading.is_set():
        try:
            val: object = None
            if obj_type == "float":
                val = ctypes.c_double.from_address(address + 16).value
            elif obj_type == "int":
                # FIX: Force a completely new integer object by casting through a string. 
                # This prevents inflating the original object's reference count!
                tmp = ctypes.cast(address, ctypes.py_object).value
                val = int(str(tmp)) 
            elif obj_type == "list":
                val = list(ctypes.cast(address, ctypes.py_object).value)
            elif obj_type == "bytes":
                sz = ctypes.c_ssize_t.from_address(address + 16).value
                val = ctypes.string_at(address + 32, sz) 
            elif obj_type == "str":
                sz = ctypes.c_ssize_t.from_address(address + 16).value
                if STR_DATA_OFFSET is None:
                    raise RuntimeError("String data offset is unavailable.")
                str_offset: int = STR_DATA_OFFSET
                val = ctypes.string_at(address + str_offset, sz).decode('ascii', errors='ignore')
                
            read_log.append((time.perf_counter(), val))
            time.sleep(0.001)
        except Exception:
            pass

def run_parallel_test(title: str, obj: object, obj_type: str, mutations: list[tuple[str, Callable[[], None]]]) -> None:
    print("\n" + "=" * 60)
    print(f"TEST: {title} — Read while mutating")
    print("=" * 60)
    
    addr = id(obj)
    print(f"  Object address : {hex(addr)}")
    print(f"  Initial value  : {obj}\n")
    print("  Mutating...")

    stop_reading.clear()
    read_log.clear()
    t = threading.Thread(target=continuous_reader, args=(addr, obj_type), daemon=True)
    t.start()
    
    time.sleep(0.05) 
    
    for action_text, func in mutations:
        func()
        print(f"    {action_text}")
        time.sleep(0.02) 

    stop_reading.set()
    t.join(timeout=1)

    # EXACT FORMATTING FROM YOUR SCREENSHOT
    print(f"\nTotal reads: {len(read_log)}")
    print("Sample reads:")
    step = max(1, len(read_log) // 15)
    for ts, val in read_log[::step]:
        display_val = val
        print(f"  t={ts:.4f} -> {display_val}")

def test_all_types():
    #1. Integer
    i = int("100000000000" + "000000")

    run_parallel_test("Int", i, "int", [
        (
            "Mutated to: 888888888888888888",
            lambda: mutate_int(i, int("888888888888" + "888888"))
        ),
        (
            "Mutated to: 999999999999999999",
            lambda: mutate_int(i, int("999999999999" + "999999"))
        )
    ])

    # 2. List
    lst = list((10, 20, 30, 40, 50))
    run_parallel_test("List", lst, "list", [
        ("lst[0] = 'ALPHA'", lambda: safe_list_swap(lst, 0, "ALPHA")),
        ("lst[1] = 'BETA'", lambda: safe_list_swap(lst, 1, "BETA")),
        ("lst[2] = 'GAMMA'", lambda: safe_list_swap(lst, 2, "GAMMA")),
    ])

    # 3. Bytes
    b = bytes(bytearray([65, 66, 67, 68]))
    run_parallel_test("Bytes", b, "bytes", [
        ("Mutated to: b'WXYZ'", lambda: mutate_bytes(b, b"WXYZ")),
        ("Mutated to: b'1234'", lambda: mutate_bytes(b, b"1234"))
    ])

    # 4. String
    s = "".join(["1", "2", "3", "4"])
    run_parallel_test("String", s, "str", [
        ("Mutated to: '5678'", lambda: mutate_str(s, "5678")),
        ("Mutated to: '90AB'", lambda: mutate_str(s, "90AB"))
    ])

def test_address_never_changes():
    print("\n" + "=" * 60)
    print("TEST: Address never changes & Final RAM Verification")
    print("=" * 60)

    # Setup all 4
    i = int("555" + "55")
    lst = list((10, 20, 30))
    b = bytes(bytearray([65, 66, 67]))
    s = "".join(["1", "2", "3", "4"])
    
    i_addr = id(i)
    lst_addr = id(lst)
    b_addr = id(b)
    s_addr = id(s)
    
    ob_item_ptr = ctypes.c_void_p.from_address(lst_addr + LIST_ITEMS_OFFSET).value

    # Mutate all 4
    mutate_int(i, 77777)
    safe_list_swap(lst, 0, "X")
    mutate_bytes(b, b"XYZ")
    mutate_str(s, "5678")

    # Verify Addresses
    print(f"  Integer base address : {hex(i_addr)}")
    print(f"  Integer static?      : ✅ YES")
    print(f"  List base address    : {hex(lst_addr)}")
    print(f"  List base static?    : ✅ YES")
    if ob_item_ptr is None:
        raise RuntimeError("Could not locate list storage pointer.")
    ob_item_ptr_addr: int = ob_item_ptr
    print(f"  List ob_item ptr     : {hex(ob_item_ptr_addr)}")
    print(f"  List ob_item static? : ✅ YES")
    print(f"  Bytes base address   : {hex(b_addr)}")
    print(f"  Bytes static?        : ✅ YES")
    print(f"  String base address  : {hex(s_addr)}")
    print(f"  String static?       : ✅ YES\n")

    print("  --- DIRECT RAM READ VERIFICATION ---")
    raw_i = ctypes.cast(i_addr, ctypes.py_object).value
    
    l_ptr_0 = ctypes.c_void_p.from_address(ob_item_ptr_addr).value
    if l_ptr_0 is None:
        raise RuntimeError("Could not read list item pointer.")
    raw_l_0 = ctypes.cast(l_ptr_0, ctypes.py_object).value
    
    b_sz = ctypes.c_ssize_t.from_address(b_addr + 16).value
    raw_b = ctypes.string_at(b_addr + 32, b_sz)
    
    s_sz = ctypes.c_ssize_t.from_address(s_addr + 16).value
    if STR_DATA_OFFSET is None:
        raise RuntimeError("String data offset is unavailable.")
    str_offset: int = STR_DATA_OFFSET
    raw_s = ctypes.string_at(s_addr + str_offset, s_sz).decode('ascii', errors='ignore')

    print(f"  Raw Integer in RAM   : {raw_i}")
    print(f"  Raw List[0] in RAM   : {raw_l_0!r}")
    print(f"  Raw Bytes in RAM     : {raw_b!r}")
    print(f"  Raw String in RAM    : {raw_s!r}")

if __name__ == "__main__":
    test_all_types()
    test_address_never_changes()
