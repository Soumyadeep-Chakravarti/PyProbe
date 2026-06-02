import ctypes
import os


def is_readable_ptr(ptr) -> bool:
    """
    Check if pointer is readable without causing a hard OS-level crash.
    """
    # 1. Filter out obvious non-pointers (like small integers such as ob_size=3).
    # Any address below 64KB (0x10000) is universally unmapped in modern OSs.
    if not isinstance(ptr, int) or ptr < 0x10000:
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


def _discover_offset(obj, known_values: list) -> int:
    """
    Dynamically discover the offset of fields in any Python object
    by scanning raw RAM bytes.
    No hardcoding, no version checks.
    """
    obj_addr = id(obj)
    expected = [id(v) for v in known_values]

    for offset in range(16, 128, 8):
        match = True
        for i, expected_addr in enumerate(expected):
            ptr = ctypes.c_void_p.from_address(
                obj_addr + offset + (i * 8)
            ).value
            if ptr != expected_addr:
                match = False
                break

        if match:
            return offset

    raise RuntimeError(
        f"Could not discover offset for {type(obj).__name__}"
    )


def _discover_tuple_items_offset() -> int:
    """
    Discover where tuple items start in memory.
    Uses known sentinel values to find their addresses in tuple struct.
    """
    s1, s2, s3 = 1000001, 1000002, 1000003
    tup = (s1, s2, s3)
    return _discover_offset(tup, [s1, s2, s3])


def _discover_list_items_offset() -> int:
    """
    Discover the offset of ob_item pointer in list struct.
    Lists store items indirectly via ob_item pointer.
    We find ob_item pointer first, then verify items are there.
    """
    s1, s2, s3 = 2000001, 2000002, 2000003
    lst = [s1, s2, s3]

    lst_addr = id(lst)
    expected = [id(s1), id(s2), id(s3)]

    for offset in range(16, 64, 8):
        ob_item_ptr = ctypes.c_void_p.from_address(
            lst_addr + offset
        ).value

        if not is_readable_ptr(ob_item_ptr):
            continue

        try:
            p0 = ctypes.c_void_p.from_address(ob_item_ptr).value
            p1 = ctypes.c_void_p.from_address(ob_item_ptr + 8).value
            p2 = ctypes.c_void_p.from_address(ob_item_ptr + 16).value

            if p0 == expected[0] and p1 == expected[1] and p2 == expected[2]:
                return offset
        except Exception:
            continue

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
        ptr = ctypes.c_void_p.from_address(
            st_addr + offset
        ).value

        if ptr == expected_addr:
            return offset

    raise RuntimeError("Could not discover set items offset!")


def _discover_str_data_offset() -> int:
    """
    Discover where string character data starts in memory.
    Compact ASCII strings store their data inline after the object header.
    """
    # Create a non-interned string with known content
    s = "".join(["A", "B", "C", "D"])  # Forces dynamic string creation
    s_addr = id(s)
    expected = b"ABCD"

    # Scan for the character data (typically at offset 48 or 56)
    for offset in range(32, 80, 8):
        try:
            # Read bytes at this offset
            raw = ctypes.string_at(s_addr + offset, 4)
            if raw == expected:
                return offset
        except Exception:
            continue

    raise RuntimeError("Could not discover string data offset!")


def _discover_dict_entry_layout() -> dict:
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

    ma_keys_ptr = None
    ma_keys_offset = None
    v1_offset_in_keys = None

    # Step 1: Find ma_keys pointer in dict struct
    for offset in range(16, 64, 8):
        ptr = ctypes.c_void_p.from_address(d_addr + offset).value

        if not is_readable_ptr(ptr):
            continue

        # Try to find v1 inside this pointer
        for inner in range(0, 200, 8):
            try:
                if not is_readable_ptr(ptr + inner):
                    continue
                val = ctypes.c_void_p.from_address(
                    ptr + inner
                ).value
                if val == expected_v1:
                    ma_keys_ptr = ptr
                    ma_keys_offset = offset
                    v1_offset_in_keys = inner
                    break
            except Exception:
                continue

        if ma_keys_ptr is not None:
            break

    if ma_keys_ptr is None or v1_offset_in_keys is None:
        raise RuntimeError("Could not find ma_keys or v1!")

    # Step 2: Find v2 offset inside ma_keys
    v2_offset_in_keys = None
    for inner in range(0, 200, 8):
        try:
            if not is_readable_ptr(ma_keys_ptr + inner):
                continue
            val = ctypes.c_void_p.from_address(
                ma_keys_ptr + inner
            ).value
            if val == expected_v2:
                v2_offset_in_keys = inner
                break
        except Exception:
            continue

    if v2_offset_in_keys is None:
        raise RuntimeError("Could not find v2 in ma_keys!")

    entry_size = v2_offset_in_keys - v1_offset_in_keys

    return {
        "ma_keys_offset": ma_keys_offset,
        "first_value_offset": v1_offset_in_keys,
        "entry_size": entry_size
    }


def _fmt_offset(val):
    return f"+{val}" if val is not None else "None"


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
    DICT_LAYOUT = _discover_dict_entry_layout()
    print(f"Dict OK: {DICT_LAYOUT}")
except Exception as e:
    print(f"Dict FAILED: {e}")
    DICT_LAYOUT = None

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