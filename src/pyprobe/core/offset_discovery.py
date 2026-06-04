import ctypes
import os
import sys
from typing import Dict, List, Optional


def is_readable_ptr(ptr: int) -> bool:
    """
    Check if pointer is readable without causing a hard OS-level crash.
    """
    # 1. Filter out obvious non-pointers (like small integers such as ob_size=3).
    # Any address below 64KB (0x10000) is universally unmapped in modern OSs.
    if ptr < 0x10000:
        return False

    # 2. On Windows, dereferencing invalid high memory STILL causes an Access 
    # Violation that bypasses Python's try/except. We must use IsBadReadPtr.
    if os.name == 'nt':
        try:
            # IsBadReadPtr returns 0 if the process HAS read access.
            if ctypes.windll.kernel32.IsBadReadPtr(ctypes.c_void_p(ptr), 8) != 0:
                return False
        except Exception:
            pass

    # 3. Standard fallback check
    try:
        ctypes.c_void_p.from_address(ptr).value
        return True
    except Exception:
        return False


def _find_pattern_in_memory(
    base_addr: int,
    pattern: List[int],
    start_offset: int = 0,
    end_offset: int = 200,
    step: int = 8
) -> Optional[int]:
    """
    Search memory starting at base_addr for a sequence of values in pattern.
    Each value is expected at base_addr + offset + i*step.
    Returns the offset where the pattern starts, or None if not found.
    """
    for offset in range(start_offset, end_offset, step):
        match = True
        for i, expected_val in enumerate(pattern):
            addr = base_addr + offset + (i * step)
            try:
                val = ctypes.c_void_p.from_address(addr).value
                if val != expected_val:
                    match = False
                    break
            except Exception:
                match = False
                break
        if match:
            return offset
    return None


def _discover_offset(
    obj_addr: int,
    known_values: List[int],
    start_offset: int = 16,
    end_offset: int = 128,
    step: int = 8
) -> int:
    """
    Dynamically discover the offset of fields in any Python object
    by scanning raw RAM bytes for a sequence of known values.
    """
    offset = _find_pattern_in_memory(
        obj_addr, known_values, start_offset, end_offset, step
    )
    if offset is None:
        raise RuntimeError(
            f"Could not discover offset for {hex(obj_addr)}"
        )
    return offset


def _discover_tuple_items_offset() -> int:
    """
    Discover where tuple items start in memory.
    Uses known sentinel values to find their addresses in tuple struct.
    """
    s1, s2, s3 = 1000001, 1000002, 1000003
    tup = (s1, s2, s3)
    obj_addr = id(tup)
    expected = [id(s1), id(s2), id(s3)]
    return _discover_offset(obj_addr, expected)


def _discover_list_items_offset() -> int:
    """
    Discover the offset of ob_item pointer in list struct.
    Lists store items indirectly via ob_item pointer.
    We find ob_item pointer first, then verify items are there.
    """
    s1, s2, s3 = 2000001, 2000002, 2000003
    lst = [s1, s2, s3]
    lst_addr = id(lst)
    expected_item_ids = [id(s1), id(s2), id(s3)]

    # First, find a pointer within the list struct that points to readable memory
    for ptr_offset in range(16, 64, 8):
        ptr_val = ctypes.c_void_p.from_address(lst_addr + ptr_offset).value
        if ptr_val is None or not is_readable_ptr(ptr_val):  # Add this guard
            continue

        # Check if the memory pointed to contains our expected item IDs
        item_offset = _find_pattern_in_memory(
            ptr_val, expected_item_ids, start_offset=0, end_offset=100, step=8
        )
        if item_offset is not None:
            return ptr_offset

    raise RuntimeError("Could not discover list items offset!")


def _discover_set_items_offset() -> int:
    """
    Discover where set items start in memory.
    Uses single sentinel since sets are unordered.
    Scans set struct for sentinel address.
    """
    s1 = 3000001
    st = {s1}
    st_addr = id(st)
    expected_addr = id(s1)

    for offset in range(16, 128, 8):
        ptr = ctypes.c_void_p.from_address(st_addr + offset).value
        if ptr == expected_addr:
            return offset

    raise RuntimeError("Could not discover set items offset!")


def _discover_dict_entry_layout() -> Dict[str, Optional[int]]:
    """
    Discover dict internal layout from RAM bytes.
    No hardcoding, no version checks.
    """
    v1 = 4000001
    v2 = 4000002
    d = {"key1": v1, "key2": v2}
    d_addr = id(d)
    expected_v1 = id(v1)
    expected_v2 = id(v2)

    ma_keys_ptr: Optional[int] = None
    ma_keys_offset: Optional[int] = None
    v1_offset_in_keys: Optional[int] = None

    # Step 1: Find ma_keys pointer in dict struct
    for offset in range(16, 64, 8):
        ptr = ctypes.c_void_p.from_address(d_addr + offset).value
        if ptr is None or not is_readable_ptr(ptr):
            continue

        # Try to find v1 inside this pointer
        v1_offset = _find_pattern_in_memory(
            ptr, [expected_v1], start_offset=0, end_offset=200, step=8
        )
        if v1_offset is not None:
            ma_keys_ptr = ptr
            ma_keys_offset = offset
            v1_offset_in_keys = v1_offset
            break

    if ma_keys_ptr is None or v1_offset_in_keys is None:
        raise RuntimeError("Could not find ma_keys or v1!")

    # Step 2: Find v2 offset inside ma_keys
    v2_offset_in_keys = _find_pattern_in_memory(
        ma_keys_ptr, [expected_v2], start_offset=0, end_offset=200, step=8
    )
    if v2_offset_in_keys is None:
        raise RuntimeError("Could not find v2 in ma_keys!")

    entry_size = v2_offset_in_keys - v1_offset_in_keys

    return {
        "ma_keys_offset": ma_keys_offset,
        "first_value_offset": v1_offset_in_keys,
        "entry_size": entry_size
    }


def _fmt_offset(val: Optional[int]) -> str:
    return f"+{val}" if val is not None else "None"

def _discover_str_data_offset() -> int:
    """
    Statically determines the internal memory offset where the raw character data 
    begins inside a Python string object wrapper.
    
    Adhering to strict input validation, it checks the internal runtime environment 
    boundaries before computing offsets using structural size constants.
    """
    # Defensive programming: ensure we are operating within a standard 64-bit architecture
    if sys.maxsize <= 2**32:
        raise NotImplementedError("32-bit architectures are not supported by PyProbe's safety model.")

    # Create a simple dynamic anchor string to analyze structural layout
    anchor = "A"
    anchor_address = id(anchor)
    
    # In CPython 64-bit, a short ASCII string uses the PyASCIIObject/PyCompactUnicodeObject struct.
    # The character array is appended immediately after the standard header fields.
    # For a standard ASCII/Latin-1 compact string, this structural offset is 48 bytes.
    expected_offset = 48
    
    try:
        # Validate that the character data ('A' -> ASCII 65) is exactly where we expect it
        target_byte = ctypes.c_char.from_address(anchor_address + expected_offset).value
        
        if target_byte == b'A':
            return expected_offset
        else:
            # Fallback/Diagnostic mapping if the runtime layout differs slightly due to specific micro-versions
            # Scan a safe, localized window to prevent out-of-bounds segmentation faults
            for scan_offset in range(24, 72, 8):
                if ctypes.c_char.from_address(anchor_address + scan_offset).value == b'A':
                    return scan_offset
            raise MemoryError("Unable to securely verify string layout boundaries.")
            
    except Exception as err:
        raise RuntimeError(f"Safety constraint violated during layout verification: {err}")

# ──────────────────────────────────────────────────────
# Run once at module load time
# ──────────────────────────────────────────────────────

print("Testing tuple...")
TUPLE_ITEMS_OFFSET = _discover_tuple_items_offset()
print(f"Tuple OK: {_fmt_offset(TUPLE_ITEMS_OFFSET)}")

print("Testing list...")
LIST_ITEMS_OFFSET = _discover_list_items_offset()
print(f"List OK: {_fmt_offset(LIST_ITEMS_OFFSET)}")

print("Testing set...")
SET_ITEMS_OFFSET = _discover_set_items_offset()
print(f"Set OK: {_fmt_offset(SET_ITEMS_OFFSET)}")

print("Testing dict...")
try:
    dict_layout = _discover_dict_entry_layout()
    print(f"Dict OK: {dict_layout}")
except Exception as e:
    print(f"Dict FAILED: {e}")
    dict_layout = None

# Assign to the constant exactly once at the very end
DICT_LAYOUT = dict_layout

print("Testing str...")
try:
    STR_DATA_OFFSET = _discover_str_data_offset()
    print(f"Str OK: {_fmt_offset(STR_DATA_OFFSET)}")
except Exception as e:
    print(f"Str FAILED: {e}")
    STR_DATA_OFFSET = None

# ──────────────────────────────────────────────────────
# Convenience variables
# ──────────────────────────────────────────────────────
DICT_MA_KEYS_OFFSET   = DICT_LAYOUT["ma_keys_offset"] if DICT_LAYOUT else None
DICT_FIRST_VAL_OFFSET = DICT_LAYOUT["first_value_offset"] if DICT_LAYOUT else None
DICT_ENTRY_SIZE       = DICT_LAYOUT["entry_size"] if DICT_LAYOUT else None


if __name__ == "__main__":
    print()
    print("=" * 40)
    print("Discovered offsets:")
    print(f"  Tuple items offset   : {_fmt_offset(TUPLE_ITEMS_OFFSET)}")
    print(f"  List ob_item offset  : {_fmt_offset(LIST_ITEMS_OFFSET)}")
    print(f"  Set items offset     : {_fmt_offset(SET_ITEMS_OFFSET)}")
    print()
    print("  Dict layout:")
    print(f"    ma_keys offset     : {_fmt_offset(DICT_MA_KEYS_OFFSET)}")
    print(f"    first value offset : {_fmt_offset(DICT_FIRST_VAL_OFFSET)}")
    print(f"    entry size         : {DICT_ENTRY_SIZE if DICT_ENTRY_SIZE else 'None'} bytes")
    print()
    print(f"  Str data offset     : {_fmt_offset(STR_DATA_OFFSET)}")
    print("=" * 40)