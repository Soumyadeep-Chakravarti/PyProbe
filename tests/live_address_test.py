import threading
import time
import ctypes

# Adjust these imports if your exact class names differ
from pyprobe.core.Scalpel import mutate_float, safe_list_swap
from pyprobe.core.offset_discovery import LIST_ITEMS_OFFSET

# ── Shared state ──────────────────────────────────────────
stop_reading = threading.Event()
read_log     = []

# ── Thread 1: Continuous Reader ───────────────────────────
def continuous_reader(address, obj_type):
    """
    Reads memory at given address continuously.
    Extracts raw values to avoid inflating Python reference counts.
    """
    while not stop_reading.is_set():
        try:
            if obj_type == "float":
                # Read the raw C-double at offset +16 directly
                value = ctypes.c_double.from_address(address + 16).value
            elif obj_type == "list":
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
    
    print(f"  Object address : {hex(addr)}")
    print(f"  Initial value  : {f}\n")

    stop_reading.clear()
    read_log.clear()
    reader = threading.Thread(target=continuous_reader, args=(addr, "float"), daemon=True)
    reader.start()
    time.sleep(0.05)

    print("  Mutating...")
    mutations = [999.99, 3.14, 42.0, 777.77]
    for val in mutations:
        mutate_float(f, val)
        print(f"    Mutated to: {val}")
        time.sleep(0.02)

    stop_reading.set()
    reader.join(timeout=1)

    print(f"\n  Total reads: {len(read_log)}")
    print("  Sample reads:")
    for ts, val in read_log[::5]:
        print(f"    t={ts:.4f} → {val}")

# ── Test 2: List ──────────────────────────────────────────
def test_list_parallel():
    print("\n" + "=" * 55)
    print("TEST 2: List — Read while mutating")
    print("=" * 55)

    lst  = list((10, 20, 30, 40, 50))
    addr = id(lst)

    print(f"  Object address : {hex(addr)}")
    print(f"  Initial value  : {lst}\n")

    stop_reading.clear()
    read_log.clear()
    reader = threading.Thread(target=continuous_reader, args=(addr, "list"), daemon=True)
    reader.start()
    time.sleep(0.05)

    print("  Mutating...")
    swaps = [(0, "ALPHA"), (1, "BETA"), (2, "GAMMA"), (3, "DELTA"), (4, "EPSILON")]
    for idx, val in swaps:
        safe_list_swap(lst, idx, val)
        print(f"    lst[{idx}] = {val!r}")
        time.sleep(0.02)

    stop_reading.set()
    reader.join(timeout=1)

    print(f"\n  Total reads: {len(read_log)}")
    print("  Sample reads:")
    for ts, val in read_log[::5]:
        print(f"    t={ts:.4f} → {val}")

# ── Test 3: Address consistency check & RAM Verification ──
def test_address_never_changes():
    print("\n" + "=" * 55)
    print("TEST 3: Address never changes & Final RAM Verification")
    print("=" * 55)

    f = float("555." + "55")
    f_addr_before = id(f)
    
    lst = list((10, 20, 30))
    lst_addr_before = id(lst)
    ob_item_before = ctypes.c_void_p.from_address(lst_addr_before + LIST_ITEMS_OFFSET).value

    f_addresses = []
    lst_addresses = []
    ob_item_addresses = []

    def record_addresses():
        while not stop_reading.is_set():
            f_addresses.append(id(f))
            lst_addresses.append(id(lst))
            current_ob_item = ctypes.c_void_p.from_address(id(lst) + LIST_ITEMS_OFFSET).value
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
    
    print(f"  List base address       : {hex(lst_addr_before)}")
    print(f"  List base static?       : {'✅ YES' if lst_all_same else '❌ NO'}")
    print(f"  List ob_item ptr        : {hex(ob_item_before)}")
    print(f"  List ob_item static?    : {'✅ YES' if ob_item_all_same else '❌ NO'}")

    print("\n  --- DIRECT RAM READ VERIFICATION ---")
    
    # 1. Read Float raw memory at +16
    final_float_ram = ctypes.c_double.from_address(f_addr_before + 16).value
    print(f"  Raw Float in RAM        : {final_float_ram}")

    # 2. Read List ob_item pointer, then read the array slots directly
    final_ob_item_ptr = ctypes.c_void_p.from_address(lst_addr_before + LIST_ITEMS_OFFSET).value
    
    # Read the 3 pointer slots inside the array (64-bit = 8 bytes each)
    ptr_0 = ctypes.c_void_p.from_address(final_ob_item_ptr).value
    ptr_1 = ctypes.c_void_p.from_address(final_ob_item_ptr + 8).value
    ptr_2 = ctypes.c_void_p.from_address(final_ob_item_ptr + 16).value
    
    # Cast pointers back to Python objects to show what sits at that memory address
    val_0 = ctypes.cast(ptr_0, ctypes.py_object).value
    val_1 = ctypes.cast(ptr_1, ctypes.py_object).value
    val_2 = ctypes.cast(ptr_2, ctypes.py_object).value
    
    print(f"  Raw List array in RAM   : [{val_0!r}, {val_1!r}, {val_2!r}]")

# ── Run all ───────────────────────────────────────────────
if __name__ == "__main__":
    test_float_parallel()
    test_list_parallel()
    test_address_never_changes()