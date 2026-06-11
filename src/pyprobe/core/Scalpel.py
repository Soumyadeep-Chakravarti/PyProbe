"""
PyProbe Scalpel Module
======================
Phase 2: Controlled memory mutation with strict safety guarantees.
Dynamically maps memory layouts to survive CPython version changes.
Includes CPython 3.12+ PyLongObject bitfield fixes.
"""

import ctypes
import types
import gc
import sys
from contextlib import contextmanager
from typing import Tuple, Any

from pyprobe.core.offset_discovery import (
    LIST_ITEMS_OFFSET,
    DICT_LAYOUT,
    STR_DATA_OFFSET
)
from pyprobe.core.common import (
    PyProbeError,
    PyProbeIntegrityError,
    PyProbeSafetyError,
    PyProbeSecurityError,
)
from pyprobe.core.safety import (
    comprehensive_safety_check,
    validate_write_access,
    snapshot,
    verify,
)

# Globally cache the memory addresses of Python's small integers at load time
SMALL_INT_ADDRS = {id(i) for i in range(-5, 257)}

# ── Import from Phase 1 ────────────────────────────────────────────────────


# ── Constants ──────────────────────────────────────────────────────────────
IMMORTAL_REFCOUNT_THRESHOLD = 1 << 30
SMALL_INT_MIN = -5
SMALL_INT_MAX = 256

# Base-2^30 math for CPython 64-bit integers
SHIFT = 30
MASK  = (1 << SHIFT) - 1


# ── GC Control & Safety ────────────────────────────────────────────────────

def _get_refcount(addr: int) -> int:
    """Read actual refcount directly from RAM."""
    return ctypes.c_ssize_t.from_address(addr).value


@contextmanager
def gc_suspended():
    """Temporarily disable GC during mutation."""
    was_enabled = gc.isenabled()
    if was_enabled:
        gc.disable()
    try:
        yield
    finally:
        if was_enabled:
            gc.enable()


def is_safe_to_mutate(obj: Any, stack_depth: int = 3) -> Tuple[bool, str]:
    """
    Master safety check before ANY memory mutation.

    Checks (in order):
        1. Immortal objects     (None, True, False)    → NEVER
        2. Cached integers      (-5 to 256)            → NEVER
        3. Interned strings     (identifiers, len <= 1) → NEVER
        4. Type objects         (int, str, list...)    → NEVER
        5. Shared objects       (refcount too high)    → NEVER

    Returns:
        (True,  "Safe")    → mutation allowed
        (False, "reason")  → mutation blocked
    """
    addr     = id(obj)
    refcount = _get_refcount(addr)

    # Rule 1: Immortal
    if refcount > IMMORTAL_REFCOUNT_THRESHOLD:
        return False, "Object is immortal"

    # Rule 2: Cached integer (Using Address-based check to prevent post-mutation false positives!)
    if isinstance(obj, int) and id(obj) in SMALL_INT_ADDRS:
        return False, "Small int cache"

    # Rule 3: Interned string
    if isinstance(obj, str) and (len(obj) <= 1 or obj.isidentifier()):
        return False, "Likely interned string"

    # Rule 4: Type object
    if isinstance(obj, type):
        return False, "Type object"

    # Rule 5: Shared object
    expected_refs = 1 + stack_depth
    if refcount > expected_refs:
        return False, f"Shared object (refs: {refcount}, expected {expected_refs})"

    # GC threshold check — collect if needed before mutation
    if gc.isenabled() and gc.get_threshold()[0] > 0:
        if gc.get_count()[0] > gc.get_threshold()[0]:
            _ = gc.collect()

    return True, "Safe"


def assert_safe(obj: Any, stack_depth: int = 3, verify_after: bool = True) -> None:
    """
    Phase 2 safety gate: comprehensive pre-mutation checks.

    Runs:
        1. Enhanced detection (types, modules, code, functions, immortal, interned, cached)
        2. Shared object detection (refcount too high)
        3. Address bounds checking (validate_write_access)

    Args:
        obj: The object to check.
        stack_depth: Expected stack depth for shared-object heuristic.
        verify_after: Reserved for future use (currently unused here).
    """
    # Phase 2: enhanced detection (HARD + SOFT blocks)
    comprehensive_safety_check(obj)

    # Shared object detection (original rule 5 from is_safe_to_mutate)
    addr     = id(obj)
    refcount = _get_refcount(addr)
    expected_refs = 1 + stack_depth
    if refcount > expected_refs:
        raise PyProbeSafetyError(
            f"Shared object (refs: {refcount}, expected {expected_refs})"
        )


# ── Transaction ─────────────────────────────────────────────────────────────

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable, Sequence


class TransactionError(PyProbeError):
    """Raised when a transaction operation fails."""


@dataclass
class Transaction:
    """
    Copy-on-write transaction with rollback support.

    Captures pre-mutation snapshots of each object. On rollback, mutations
    are reverted by restoring original values from those snapshots.

    Usage::

        with transaction() as tx:
            mutate_float(f, 999.99)   # tracked automatically
            mutate_int(x, 42)         # tracked automatically
            # on exception → all mutations rolled back
    """
    _revert_ops: list[tuple[Callable, tuple]] = field(default_factory=list)
    _committed: bool = False

    def _record(self, revert_fn: Callable, *args) -> None:
        self._revert_ops.append((revert_fn, args))

    def commit(self) -> None:
        """Discard all snapshots — mutations become permanent."""
        self._revert_ops.clear()
        self._committed = True

    def rollback(self) -> None:
        """Revert all tracked mutations in reverse order."""
        if self._committed:
            return
        for fn, args in reversed(self._revert_ops):
            try:
                fn(*args)
            except Exception:
                pass  # best-effort rollback
        self._revert_ops.clear()

    # ── Revert helpers (one per type) ───────────────────────────────────

    @staticmethod
    def _revert_float(target: float, snap: "ObjectSnapshot") -> None:
        ctypes.c_double.from_address(id(target) + 16).value = snap.float_value

    @staticmethod
    def _revert_int(target: int, snap: "ObjectSnapshot") -> None:
        addr = id(target)
        ctypes.c_ssize_t.from_address(addr + 16).value = snap.lv_tag  # type: ignore
        if snap.digit_data:
            ArrayType = ctypes.c_uint32 * len(snap.digit_data)
            digit_array = ArrayType.from_address(addr + 24)
            for i, val in enumerate(snap.digit_data):
                digit_array[i] = val

    @staticmethod
    def _revert_list_slot(target: list, index: int, old_obj_id: int) -> None:
        list_addr = id(target)
        ob_item = ctypes.c_void_p.from_address(list_addr + LIST_ITEMS_OFFSET).value
        slot_addr = ob_item + (index * 8)
        old_ptr = ctypes.c_void_p.from_address(slot_addr).value
        if old_obj_id:
            ctypes.c_ssize_t.from_address(old_obj_id).value += 1  # INCREF old
        ctypes.c_void_p.from_address(slot_addr).value = old_obj_id  # SWAP
        if old_ptr:
            ctypes.c_ssize_t.from_address(old_ptr).value -= 1  # DECREF current

    @staticmethod
    def _revert_dict_slot(target: dict, key: Any, old_val_id: int) -> None:
        # After swap, the slot holds the NEW value. Find it and swap back.
        current_val_id = id(target[key])

        d_addr = id(target)
        assert DICT_LAYOUT is not None
        ma_keys_ptr = ctypes.c_void_p.from_address(
            d_addr + DICT_LAYOUT["ma_keys_offset"]
        ).value
        assert ma_keys_ptr is not None
        entry_size = DICT_LAYOUT["entry_size"]
        scan_limit = len(target) * entry_size * 4

        for offset in range(0, scan_limit, 8):
            try:
                ptr = ctypes.c_void_p.from_address(ma_keys_ptr + offset).value
                if ptr == current_val_id:
                    candidate = ma_keys_ptr + offset
                    if candidate < 0x1000 or candidate & 7:
                        continue
                    ctypes.c_ssize_t.from_address(old_val_id).value += 1
                    ctypes.c_void_p.from_address(candidate).value = old_val_id
                    ctypes.c_ssize_t.from_address(current_val_id).value -= 1
                    return
            except Exception:
                pass

    @staticmethod
    def _revert_bytes(target: bytes, snap: "ObjectSnapshot") -> None:
        addr = id(target)
        BYTES_VAL_OFFSET = 32
        with gc_suspended():
            ctypes.memmove(addr + BYTES_VAL_OFFSET, snap.raw_bytes, len(snap.raw_bytes))
            ctypes.c_ssize_t.from_address(addr + 24).value = snap.hash_cache

    @staticmethod
    def _revert_str(target: str, snap: "ObjectSnapshot") -> None:
        addr = id(target)
        if STR_DATA_OFFSET is None:
            return
        with gc_suspended():
            ctypes.memmove(addr + STR_DATA_OFFSET, snap.raw_bytes, len(snap.raw_bytes))
            ctypes.c_ssize_t.from_address(addr + 24).value = snap.hash_cache


# Module-level transaction stack
_current_tx: list[Transaction] = []


@contextmanager
def transaction():
    """
    Context manager that enables rollback for all mutations inside it.

    Mutations performed while this is active are automatically tracked.
    On clean exit the transaction is committed; on exception it is rolled back.

    Returns:
        Transaction object — call .commit() early to discard rollback history.
    """
    tx = Transaction()
    _current_tx.append(tx)
    try:
        yield tx
        tx.commit()
    except Exception:
        tx.rollback()
        raise
    finally:
        _current_tx.pop()


def _track_revert(revert_fn: Callable, *args) -> None:
    """Called by each mutator to record a revert operation if inside a transaction."""
    if _current_tx:
        _current_tx[-1]._record(revert_fn, *args)


# ── Mutators ───────────────────────────────────────────────────────────────

def mutate_float(target_float: float, new_value: float, safe: bool = True) -> None:
    """
    Overwrite the underlying C double of a Python float.

    Layout:
        +0  refcount
        +8  type pointer
        +16 ob_fval (IEEE 754 double) ← we write here
    """
    if safe:
        assert_safe(target_float, stack_depth=5)

    addr = id(target_float)
    validate_write_access(addr + 16, 8)
    snap = snapshot(target_float)

    double_ptr = ctypes.c_double.from_address(addr + 16)

    with gc_suspended():
        double_ptr.value = new_value

    verify(target_float, snap, strict=True)
    _track_revert(Transaction._revert_float, target_float, snap)


def mutate_int(target_int: int, new_value: int, safe: bool = True) -> None:
    """
    Mutate a target integer in-place.
    Handles CPython 3.12+ lv_tag bitfield encoding.

    Constraint:
        new_value must fit in same number of digits as target_int.
        Cannot grow the integer — would require reallocation.

    Layout (3.12+):
        +0  refcount
        +8  type pointer
        +16 lv_tag (size << 3 | sign)
        +24 digit array (uint32[])
    """
    if safe:
        assert_safe(target_int, stack_depth=5)
    if target_int == new_value:
        return

    addr        = id(target_int)
    validate_write_access(addr + 16, 8)
    snap = snapshot(target_int)

    ob_size_ptr = ctypes.c_ssize_t.from_address(addr + 16)

    # Decode current capacity
    if sys.version_info >= (3, 12):
        current_capacity = ob_size_ptr.value >> 3
    else:
        current_capacity = abs(ob_size_ptr.value)

    # Calculate digits needed for new value
    new_digits: list[int] = []
    temp = abs(new_value)
    while temp > 0:
        new_digits.append(temp & MASK)
        temp >>= SHIFT

    required_capacity = len(new_digits)

    if required_capacity > current_capacity:
        raise MemoryError(
            f"Overflow prevented: target capacity is {current_capacity} digits, "
            f"but {new_value} requires {required_capacity}."
        )

    # Encode new size/tag (CPython 3.12+ lv_tag)
    # lv_tag = (digit_count << 3) | sign_tag | interned_bit
    #   sign_tag:  positive=0, zero=1, negative=2
    #   interned_bit: bit 2 (value 4), set for cached small ints
    if sys.version_info >= (3, 12):
        if new_value == 0:
            new_ob_size = 5  # (0 << 3) | 1  — zero is always cached
        else:
            sign_tag = 0 if new_value > 0 else 2
            new_ob_size = (required_capacity << 3) | sign_tag
    else:
        if new_value == 0:
            new_ob_size = 0
        elif new_value > 0:
            new_ob_size = required_capacity
        else:
            new_ob_size = -required_capacity

    with gc_suspended():
        ob_size_ptr.value = new_ob_size
        if required_capacity != 0:
            ArrayType   = ctypes.c_uint32 * required_capacity
            digit_array = ArrayType.from_address(addr + 24)
            for i, digit in enumerate(new_digits):
                digit_array[i] = digit

    verify(target_int, snap, strict=True)
    _track_revert(Transaction._revert_int, target_int, snap)


def safe_list_swap(target_list: list[Any], index: int, new_obj: Any, safe: bool = True) -> None:
    """
    Replace a list item by hot-swapping the memory pointer.

    Steps:
        1. Find ob_item pointer (discovered dynamically)
        2. INCREF new object
        3. Swap pointer
        4. DECREF old object

    Layout:
        list_addr + LIST_ITEMS_OFFSET → ob_item pointer
        ob_item + (index * 8)         → slot to swap
    """
    if safe:
        assert_safe(target_list, stack_depth=5)
    if index < 0 or index >= len(target_list):
        raise IndexError("List index out of range")

    list_addr    = id(target_list)
    new_obj_addr = id(new_obj)

    ob_item_ptr = ctypes.c_void_p.from_address(list_addr + LIST_ITEMS_OFFSET).value
    assert ob_item_ptr is not None
    target_slot_addr = ob_item_ptr + (index * 8)

    validate_write_access(target_slot_addr, 8)
    snap = snapshot(target_list)

    with gc_suspended():
        old_obj_ptr = ctypes.c_void_p.from_address(target_slot_addr).value
        ctypes.c_ssize_t.from_address(new_obj_addr).value += 1               # INCREF new
        ctypes.c_void_p.from_address(target_slot_addr).value = new_obj_addr  # SWAP
        if old_obj_ptr:
            ctypes.c_ssize_t.from_address(old_obj_ptr).value -= 1            # DECREF old

    verify(target_list, snap, strict=True)
    _track_revert(Transaction._revert_list_slot, target_list, index, old_obj_ptr)


def safe_dict_value_swap(target_dict: dict[Any, Any], key: Any, new_value: Any, safe: bool = True) -> None:
    """
    Find value pointer for a dict key and hot-swap it.

    Steps:
        1. Get ma_keys pointer (discovered dynamically)
        2. Scan for old value's address
        3. INCREF new value
        4. Swap pointer
        5. DECREF old value

    Layout:
        dict_addr + ma_keys_offset → ma_keys pointer
        scan ma_keys for old_val_id → target slot
    """
    if safe:
        assert_safe(target_dict, stack_depth=5)
    if key not in target_dict:
        raise KeyError(f"Key '{key}' not found.")

    d_addr       = id(target_dict)
    new_obj_addr = id(new_value)
    old_val_id   = id(target_dict[key])

    assert DICT_LAYOUT is not None
    ma_keys_ptr = ctypes.c_void_p.from_address(
        d_addr + DICT_LAYOUT["ma_keys_offset"]
    ).value
    assert ma_keys_ptr is not None

    entry_size  = DICT_LAYOUT["entry_size"]
    scan_limit  = len(target_dict) * entry_size * 4
    target_slot_addr = None

    for offset in range(0, scan_limit, 8):
        try:
            ptr = ctypes.c_void_p.from_address(ma_keys_ptr + offset).value
            if ptr == old_val_id:
                candidate = ma_keys_ptr + offset
                # Validation: reject kernel addresses, null, and unaligned pointers
                if candidate < 0x1000 or candidate & 7:
                    continue
                target_slot_addr = candidate
                break
        except Exception:
            pass

    if not target_slot_addr:
        raise PyProbeIntegrityError("Could not locate value pointer in memory.")

    validate_write_access(target_slot_addr, 8)
    snap = snapshot(target_dict)

    with gc_suspended():
        ctypes.c_ssize_t.from_address(new_obj_addr).value += 1               # INCREF new
        ctypes.c_void_p.from_address(target_slot_addr).value = new_obj_addr  # SWAP
        ctypes.c_ssize_t.from_address(old_val_id).value -= 1                 # DECREF old

    verify(target_dict, snap, strict=True)
    _track_revert(Transaction._revert_dict_slot, target_dict, key, old_val_id)


def mutate_bytes(target_bytes: bytes, new_bytes: bytes, safe: bool = True) -> None:
    """
    Overwrites the raw character array of a bytes object in RAM.
    Lengths MUST match exactly to avoid writing out of bounds.
    
    Layout:
        +0  refcount
        +8  type pointer
        +16 ob_size
        +24 ob_shash (cached hash)
        +32 ob_sval (raw byte array) ← we overwrite this block
    """
    if safe:
        assert_safe(target_bytes, stack_depth=5)

    for referrer in gc.get_referrers(target_bytes):
        if isinstance(referrer, types.CodeType):
            raise PyProbeSecurityError("SECURITY LOCKDOWN: Attempted to mutate live function bytecode (co_code).")
        
    if len(target_bytes) != len(new_bytes):
        raise PyProbeIntegrityError("Length mismatch: cannot resize allocated bytes object.")
    if target_bytes == new_bytes:
        return

    addr = id(target_bytes)
    BYTES_VAL_OFFSET = 32

    validate_write_access(addr + BYTES_VAL_OFFSET, len(target_bytes))
    snap = snapshot(target_bytes)

    with gc_suspended():
        # Overwrite the raw memory block using ctypes.memmove
        target_buffer = addr + BYTES_VAL_OFFSET
        source_buffer = id(new_bytes) + BYTES_VAL_OFFSET
        _ = ctypes.memmove(target_buffer, source_buffer, len(target_bytes))
        
        # Invalidate the cached hash by setting it to -1 (so dicts don't break)
        ctypes.c_ssize_t.from_address(addr + 24).value = -1

    verify(target_bytes, snap, strict=True)
    _track_revert(Transaction._revert_bytes, target_bytes, snap)


def mutate_str(target_str: str, new_str: str, safe: bool = True) -> None:
    """
    Overwrites the inline character array of a dynamically created, 
    non-interned Compact ASCII string in memory.
    Uses Phase 1 dynamic offset discovery.
    """
    if safe:
        assert_safe(target_str, stack_depth=5)
    if len(target_str) != len(new_str):
        raise PyProbeIntegrityError("Length mismatch: cannot resize allocated string object.")
    if target_str == new_str:
        return

    addr = id(target_str)

    if STR_DATA_OFFSET is None:
        raise PyProbeIntegrityError("String data offset was not discovered.")

    data_offset: int = STR_DATA_OFFSET

    # State validation (ensure it is Compact ASCII and not interned)
    state_flags = ctypes.c_uint32.from_address(addr + 32).value
    if (state_flags & 0x03) != 0:
        raise PyProbeSecurityError("Aborting: String is interned.")
    if ((state_flags >> 2) & 0x07) != 1:
        raise PyProbeSecurityError("Unsupported encoding. Scalpel only mutates Compact ASCII.")

    validate_write_access(addr + data_offset, len(target_str))
    snap = snapshot(target_str)

    with gc_suspended():
        target_buffer: int = addr + data_offset
        source_buffer: int = id(new_str) + data_offset
        _ = ctypes.memmove(target_buffer, source_buffer, len(target_str))
        
        # Reset the cached hash
        ctypes.c_ssize_t.from_address(addr + 24).value = -1

    verify(target_str, snap, strict=True)
    _track_revert(Transaction._revert_str, target_str, snap)


# ── Batch Mutation ──────────────────────────────────────────────────────────

def mutate_batch(
    operations: Sequence[tuple[Callable, ...]],
    safe: bool = True,
) -> None:
    """
    Execute multiple mutations atomically under a single transaction.

    If any mutation fails, all previous mutations are rolled back,
    leaving all objects in their original state.

    Args:
        operations: Sequence of ``(mutate_fn, arg1, arg2, ...)`` tuples.
        safe: Passed as a keyword argument to each mutation function.

    Raises:
        The first exception raised by any mutation.

    Example:
        >>> x = 3.14
        >>> y = 1000
        >>> lst = [1, 2, 3]
        >>> mutate_batch([
        ...     (mutate_float, x, 2.71),
        ...     (mutate_int, y, 42),
        ...     (safe_list_swap, lst, 0, 999),
        ... ])
    """
    with transaction():
        for op in operations:
            fn, *args = op
            fn(*args, safe=safe)


# ── Tests ──────────────────────────────────────────────────────────────────

def run_tests():
    print("=" * 50)
    print("PyProbe Scalpel: Phase 2 Mutation Tests")
    print("=" * 50)

    # Float
    f = float("100." + "5")
    print(f"\n[Float] Before: {f}")
    mutate_float(f, 999.99)
    print(f"[Float] After : {f}")

    # Int
    big_int = int("1" + "0" * 18)
    print(f"\n[Int] Before: {big_int}")
    mutate_int(big_int, 42)
    print(f"[Int] After : {big_int}")

    # List
    lst = list((10, 20, 30))
    print(f"\n[List] Before: {lst}")
    safe_list_swap(lst, 1, "MUTATED")
    print(f"[List] After : {lst}")

    # Dict
    d = dict(status="secure", version=1)
    print(f"\n[Dict] Before: {d}")
    safe_dict_value_swap(d, "status", "mutated")
    print(f"[Dict] After : {d}")

    # Bytes
    b = bytes(bytearray([65, 66, 67, 68]))  # b"ABCD"
    print(f"\n[Bytes] Before: {b}")
    mutate_bytes(b, b"WXYZ")
    print(f"[Bytes] After : {b}")

    # String
    s = "".join(["1", "2", "3", "4"])
    print(f"\n[Str] Before: {s}")
    mutate_str(s, "4567")
    print(f"[Str] After : {s}")

if __name__ == "__main__":
    run_tests()