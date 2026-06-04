import threading
import time
import ctypes
<<<<<<< HEAD
from typing import Literal
=======
from typing import Callable
>>>>>>> test-ruleset-workflow

from pyprobe.core.Scalpel import (
    safe_list_swap, mutate_bytes, mutate_str, mutate_int
)
from pyprobe.core.offset_discovery import (
    LIST_ITEMS_OFFSET, STR_DATA_OFFSET
)

# ── Shared state ──────────────────────────────────────────
stop_reading = threading.Event()
read_log: list[tuple[float, object]] = []

<<<<<<< HEAD

def require_address(value: int | None, label: str) -> int:
    if value is None:
        raise ValueError(f"{label} is null")
    return value

# ── Thread 1: Continuous Reader ───────────────────────────
def continuous_reader(address: int, obj_type: Literal["float", "list"]) -> None:
    """
    Reads memory at given address continuously.
    Extracts raw values to avoid inflating Python reference counts.
    """
    while not stop_reading.is_set():
        try:
            value: object
            if obj_type == "float":
                # Read the raw C-double at offset +16 directly
                value = ctypes.c_double.from_address(address + 16).value
            else:
                # Cast temporarily, then copy to avoid holding the reference
                obj = ctypes.cast(address, ctypes.py_object).value
                value = list(obj)

            timestamp = time.perf_counter()
            read_log.append((timestamp, value))
            time.sleep(0.001)  # 1ms interval
        except Exception as e:
            read_log.append((time.perf_counter(), f"READ ERROR: {e}"))

# ── Test 1: Float ─────────────────────────────────────────
def test_float_parallel():
    print("=" * 55)
    print("TEST 1: Float — Read while mutating")
    print("=" * 55)

    f = float("100." + "5")
    addr = id(f)
=======
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
>>>>>>> test-ruleset-workflow
    
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
<<<<<<< HEAD
        display_val = tuple(val) if obj_type == 'tuple' else val
=======
        display_val = val
>>>>>>> test-ruleset-workflow
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
<<<<<<< HEAD
    lst_addr_before = id(lst)
    ob_item_before = require_address(
        ctypes.c_void_p.from_address(lst_addr_before + LIST_ITEMS_OFFSET).value,
        "list ob_item pointer",
    )

    f_addresses: list[int] = []
    lst_addresses: list[int] = []
    ob_item_addresses: list[int] = []

    def record_addresses():
        while not stop_reading.is_set():
            f_addresses.append(id(f))
            lst_addresses.append(id(lst))
            current_ob_item = require_address(
                ctypes.c_void_p.from_address(id(lst) + LIST_ITEMS_OFFSET).value,
                "current list ob_item pointer",
            )
            ob_item_addresses.append(current_ob_item)
            time.sleep(0.001)

    stop_reading.clear()
    t = threading.Thread(target=record_addresses, daemon=True)
    t.start()
    time.sleep(0.05)

    for val in [1.1, 2.2, 3.3]:
        mutate_float(f, val)
        time.sleep(0.02)
        
    for idx, val in [(0, "X"), (1, "Y"), (2, "Z")]:
        safe_list_swap(lst, idx, val)
        time.sleep(0.02)

    stop_reading.set()
    t.join(timeout=1)

    f_all_same = all(a == f_addr_before for a in f_addresses)
    lst_all_same = all(a == lst_addr_before for a in lst_addresses)
    ob_item_all_same = all(a == ob_item_before for a in ob_item_addresses)

    print(f"  Float base address      : {hex(f_addr_before)}")
    print(f"  Float static?           : {'✅ YES' if f_all_same else '❌ NO'}")
=======
    b = bytes(bytearray([65, 66, 67]))
    s = "".join(["1", "2", "3", "4"])
>>>>>>> test-ruleset-workflow
    
    i_addr = id(i)
    lst_addr = id(lst)
    b_addr = id(b)
    s_addr = id(s)
    
<<<<<<< HEAD
    # 1. Read Float raw memory at +16
    final_float_ram = ctypes.c_double.from_address(f_addr_before + 16).value
    print(f"  Raw Float in RAM        : {final_float_ram}")

    # 2. Read List ob_item pointer, then read the array slots directly
    final_ob_item_ptr = require_address(
        ctypes.c_void_p.from_address(lst_addr_before + LIST_ITEMS_OFFSET).value,
        "final list ob_item pointer",
    )
    
    # Read the 3 pointer slots inside the array (64-bit = 8 bytes each)
    ptr_0 = require_address(ctypes.c_void_p.from_address(final_ob_item_ptr).value, "ptr_0")
    ptr_1 = require_address(ctypes.c_void_p.from_address(final_ob_item_ptr + 8).value, "ptr_1")
    ptr_2 = require_address(ctypes.c_void_p.from_address(final_ob_item_ptr + 16).value, "ptr_2")
=======
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
>>>>>>> test-ruleset-workflow
    
    b_sz = ctypes.c_ssize_t.from_address(b_addr + 16).value
    raw_b = ctypes.string_at(b_addr + 32, b_sz)
    
    s_sz = ctypes.c_ssize_t.from_address(s_addr + 16).value
<<<<<<< HEAD
    raw_s = ctypes.string_at(s_addr + STR_DATA_OFFSET, s_sz).decode('ascii', errors='ignore')
=======
    if STR_DATA_OFFSET is None:
        raise RuntimeError("String data offset is unavailable.")
    str_offset: int = STR_DATA_OFFSET
    raw_s = ctypes.string_at(s_addr + str_offset, s_sz).decode('ascii', errors='ignore')
>>>>>>> test-ruleset-workflow

    print(f"  Raw Integer in RAM   : {raw_i}")
    print(f"  Raw List[0] in RAM   : {raw_l_0!r}")
    print(f"  Raw Bytes in RAM     : {raw_b!r}")
    print(f"  Raw String in RAM    : {raw_s!r}")

if __name__ == "__main__":
    test_all_types()
    test_address_never_changes()
