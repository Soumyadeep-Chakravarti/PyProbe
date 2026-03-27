"""PyProbe Engine: High-speed memory introspection for CPython 3.14."""

import ctypes
import sys
from typing import Any, Dict, Optional, Tuple, Type, Union

from pyprobe.raw.headers.py_object import PyObjectHeader
from pyprobe.raw.headers.py_type import PyTypeObject
from pyprobe.raw.lenses.bytes_lens import BytesLens
from pyprobe.raw.lenses.dict_lens import DictKeysLens, DictLens
from pyprobe.raw.lenses.float_lens import FloatLens
from pyprobe.raw.lenses.int_lens import IntLens
from pyprobe.raw.lenses.list_lens import ListLens
from pyprobe.raw.lenses.set_lens import SetLens
from pyprobe.raw.lenses.str_lens import CompactUnicodeLens, StringLens
from pyprobe.raw.lenses.tuple_lens import TupleLens

# PyObject_HEAD
HEADER_SIZE = 16

# PyVarObject_HEAD
VAR_HEADER_SIZE = 24

# Industrial Singleton Discovery
_DUMMY_PTR: Optional[int] = None


def _get_dummy_ptr() -> Optional[int]:
    """Resolve the address of the internal <dummy> singleton safely."""
    global _DUMMY_PTR
    if _DUMMY_PTR is None:
        try:
            # We locate it via a temporary dict tombstone
            d = {0: 0}
            del d[0]
            addr = id(d)
            # Find ma_keys ptr at +32 (3.12+)
            keys_addr = ctypes.c_void_p.from_address(addr + 32).value
            # In 3.14, indices start at +32.
            # Entry 0 key starts at +32 + indices_size + hash_offset
            # For size 8, indices size is 8.
            # General dict has hash(8) before key
            # Total offset: 32 + 8 + 8 = 48.
            _DUMMY_PTR = ctypes.c_void_p.from_address(keys_addr + 48).value
        except Exception:
            pass
    return _DUMMY_PTR


# Architecture Guard
if ctypes.sizeof(ctypes.c_void_p) != 8:
    raise RuntimeError(
        "PyProbe currently only supports 64-bit CPython architectures."
    )

# Cached lookups for performance
_TYPE_NAME_CACHE: Dict[int, str] = {}


class Pointer:
    """Defining pointer."""

    def __init__(self, target: Any) -> None:
        """Initialize class."""
        self._target = target
        self.address: int = id(target)
        self.header = PyObjectHeader.from_address(self.address)

        type_struct = PyTypeObject.from_address(self.header.ob_type_ptr)
        self.type_name: str = type_struct.tp_name.decode('utf-8')

        # Standard PyObject_HEAD is 16 bytes. All unique data starts at +16.
        self.header_size = 16
        self.data_addr: int = self.address + self.header_size

        # Dispatcher for data extraction
        self._extractors = {
            'int': self._extract_int,
            'float': self._extract_float,
            'str': self._extract_string,
            'tuple': self._extract_tuple,
            'list': self._extract_list,
            'dict': self._extract_dict,
            'bytes': self._extract_bytes,
            'set': self._extract_set,
            'frozenset': self._extract_set,
        }

        self.lens = self._get_lens()

    def _extract_dict(
            self,
            addr: int,
            visited: Optional[set] = None,
            depth: int = 0
    ) -> dict:
        """Extract dictionary items using surgical DictLens."""
        # PyDictObject is NOT a VarObject, lens starts after PyObject_HEAD
        lens = DictLens.from_address(addr + 16)
        if not lens.ma_keys:
            return {}

        base_addr_val = ctypes.cast(lens.ma_keys, ctypes.c_void_p).value
        if not base_addr_val:
            return {}

        values_ptr = lens.ma_values
        is_split = (values_ptr is not None)
        values_array = ctypes.cast(
            values_ptr,
            ctypes.POINTER(ctypes.c_void_p)
        ) if is_split else None

        keys_addr = lens.ma_keys
        keys_obj = DictKeysLens.from_address(keys_addr)

        entries_start_offset, _, is_unicode, _ = self._get_dict_geometry(
            ctypes.cast(
                keys_addr, ctypes.POINTER(DictKeysLens)
            )
        )
        stride = self._get_entry_stride(is_unicode, is_split)

        result = {}
        dummy_ptr = _get_dummy_ptr()
        for i in range(keys_obj.dk_nentries):
            entry_addr = keys_addr + entries_start_offset + (i * stride)
            try:
                key_ptr, val_ptr = self._read_dict_entry(
                    entry_addr,
                    stride,
                    is_split,
                    values_array, i
                )
                # Skip NULL and Dummy keys
                if key_ptr and key_ptr != dummy_ptr:
                    key = self.pull_data_from_address(
                        key_ptr,
                        visited,
                        depth + 1)
                    value = self.pull_data_from_address(
                        val_ptr,
                        visited,
                        depth + 1
                    ) if val_ptr else None
                    result[key] = value
            except Exception as e:
                result[f"<error_slot_{i}>"] = str(e)
        return result

    def _get_lens(self) -> Optional[Any]:
        # Surgical views of the object body (look past the header)
        lenses: Dict[str, Type[Any]] = {
            'int': IntLens,
            'float': FloatLens,
            'list': ListLens,
            'str': StringLens,
            'dict': DictLens,
            'tuple': TupleLens,
            'bytes': BytesLens,
            'set': SetLens,
            'frozenset': SetLens,
        }
        cls = lenses.get(self.type_name)
        # Surgical grab uses the detected header size
        return cls.from_address(
            self.address + self.header_size
        ) if cls else None

    def _normalize_address(
            self,
            addr: Union[int, ctypes.c_void_p]
    ) -> Optional[int]:
        """Convert address to integer format."""
        actual_addr = addr.value if isinstance(addr, ctypes.c_void_p) else addr
        return actual_addr if actual_addr and actual_addr != 0 else None

    def _get_type_name(self, type_addr: int) -> str:
        """Cache type name lookup."""
        if type_addr not in _TYPE_NAME_CACHE:
            try:
                type_struct = PyTypeObject.from_address(type_addr)
                # tp_name is a pointer to a string.
                # We should check if it's readable.
                # Heuristic: tp_name should be > 0.
                if not type_struct.tp_name:
                    return f"<Uninitialized Type @ {hex(type_addr)}>"
                operator = type_struct.tp_name
                _TYPE_NAME_CACHE[type_addr] = operator.decode('utf-8')
            except Exception:
                return f"<Invalid Type @ {hex(type_addr)}>"
        return _TYPE_NAME_CACHE[type_addr]

    def _get_type_info(
            self,
            addr: int
    ) -> Tuple[Optional[PyObjectHeader], str]:
        """Extract header and cached type name from address with safety."""
        # Aligned? Reasonable?
        if addr < 0x1000 or addr & 0x7 != 0:
            return None, f"<Bad Address {hex(addr)}>"

        try:
            header = PyObjectHeader.from_address(addr)
            # Basic pointer validation for type_ptr
            if header.ob_type_ptr & 0x07 != 0 or header.ob_type_ptr < 0x1000:
                return header, f"<Corrupt Type @ {hex(header.ob_type_ptr)}>"

            type_name = self._get_type_name(header.ob_type_ptr)
            return header, type_name
        except Exception:
            return None, f"<Read Error {hex(addr)}>"

    def _extract_int(self, addr: int) -> int:
        """Extract integer value (PyLongObject)."""
        # lv_tag is at offset 16 in 3.12+
        tag = ctypes.c_size_t.from_address(addr + 16).value

        size = tag >> 3
        if size == 0:
            return 0

        # bit 1 is usually the sign in 3.12+ (0 positive, 1 negative)
        negative = (tag >> 1) & 0x01
        # digits start at offset 24 (after tag)
        digits_array = ctypes.cast(addr + 24, ctypes.POINTER(ctypes.c_uint32))

        result = 0
        for i in range(size):
            result += digits_array[i] * (1 << (30 * i))

        return -result if negative else result

    def _extract_float(self, addr: int) -> float:
        """Extract float value using FloatLens (surgical body view)."""
        return FloatLens.from_address(addr + 16).ob_fval

    def _extract_string(self, addr: int) -> str:
        """Extract string value using StringLens abstractions."""
        # Standard lens starts right after PyObject_HEAD (offset 16)
        lens = StringLens.from_address(addr + 16)

        kind = lens.kind
        if not lens.compact:
            return f"<non-compact str @ {hex(addr)}>"

        if lens.ascii:
            # Data starts after ASCIIObject (prefix fields only)
            # ASCIIObject body size (excluding head) is usually 32
            # 16(HEAD) + 32(LENS) = 48.
            data_offset = 16 + ctypes.sizeof(StringLens)
            encoding = 'ascii'
        else:
            # CompactUnicodeObject body size
            data_offset = 16 + ctypes.sizeof(CompactUnicodeLens)
            encoding = {
                1: 'latin1',
                2: 'utf-16',
                4: 'utf-32'}.get(
                    kind,
                    'utf-8'
                )

        try:
            char_size = 4 if kind == 4 else (2 if kind == 2 else 1)
            total_bytes = lens.length * char_size
            raw_data = ctypes.string_at(addr + data_offset, total_bytes)

            if char_size > 1:
                encoding += '-le' if sys.byteorder == 'little' else '-be'

            return raw_data.decode(encoding)
        except Exception as e:
            return f"<Error decoding str: {e}>"

    def _extract_tuple(
            self,
            addr: int,
            visited: Optional[set] = None,
            depth: int = 0
    ) -> tuple:
        """Extract tuple items with cached hash offset (3.12+ layout)."""
        size = ctypes.c_ssize_t.from_address(addr + 16).value
        # hash_cached(8) starts at +24, items start at +32
        items_array = ctypes.cast(addr + 32, ctypes.POINTER(ctypes.c_void_p))
        return tuple(self.pull_data_from_address(
            items_array[i], visited, depth + 1
        ) for i in range(size))

    def _extract_list(
            self,
            addr: int,
            visited: Optional[set] = None,
            depth: int = 0
    ) -> list:
        """Extract list items using surgical offset."""
        size = ctypes.c_ssize_t.from_address(addr + 16).value
        # Pointer to item array is at +24
        items_ptr = ctypes.c_void_p.from_address(addr + 24).value
        if not items_ptr:
            return []
        items_array = ctypes.cast(items_ptr, ctypes.POINTER(ctypes.c_void_p))
        return [self.pull_data_from_address(
            items_array[i], visited, depth + 1
        ) for i in range(size)]

    def _extract_bytes(self, addr: int) -> bytes:
        """Extract bytes data structure (after PyVarObject_HEAD)."""
        # ob_size (offset 16)
        size = ctypes.c_ssize_t.from_address(addr + 16).value
        # hash (8) + data (inline)
        # data starts at +32 (after size and hash)
        return ctypes.string_at(addr + 32, size)

    def _extract_set(
            self,
            addr: int,
            visited: Optional[set] = None,
            depth: int = 0
    ) -> set:
        """Extract set using surgical lens (starts after PyObject_HEAD)."""
        lens = SetLens.from_address(addr + self.header_size)
        result = set()
        dummy_ptr = _get_dummy_ptr()

        table_ptr = lens.table
        mask = lens.mask

        for i in range(mask + 1):
            entry = table_ptr[i]
            key_addr = entry.key
            if key_addr and key_addr != dummy_ptr:
                val = self.pull_data_from_address(key_addr, visited, depth + 1)
                result.add(val)
        return result

    def pull_data_from_address(
            self,
            addr: Union[int, ctypes.c_void_p],
            visited: Optional[set] = None, depth: int = 0
    ) -> Any:
        """Extract Python object data from memory address."""
        actual_addr = self._normalize_address(addr)
        if actual_addr is None:
            return "NULL"

        # Cycle Detection & Recursion Limit
        if visited is None:
            visited = set()

        if actual_addr in visited:
            return f"<Cycle @ {hex(actual_addr)}>"

        if depth > 100:  # Generous limit for complex heap graphs
            return f"<Max Depth @ {hex(actual_addr)}>"

        try:
            _, type_name = self._get_type_info(actual_addr)

            # track containers in visited to avoid interning false positives
            is_container = type_name in ['list', 'tuple', 'dict']
            if is_container:
                visited.add(actual_addr)

            # Use dispatcher
            extractor = self._extractors.get(type_name)
            if extractor:
                # Some extractors recurse, pass state
                if is_container:
                    return extractor(actual_addr, visited, depth)
                return extractor(actual_addr)

            return f"<{type_name} @ {hex(actual_addr)}>"
        except Exception as e:
            return f"<Error reading {hex(actual_addr)}: {e}>"

    def _get_dict_geometry(
            self,
            keys_ptr: ctypes.POINTER(DictKeysLens)
    ) -> Tuple[int, int, bool, bool]:
        """Calculate dictionary memory layout parameters using DictKeysLens."""
        keys = keys_ptr.contents
        dk_kind = keys.dk_kind

        # In 3.14, offset 9 is log2_total_indices_size
        log2_ix_total = keys.dk_log2_index_bytes
        ix_total_size = 1 << log2_ix_total

        # Header size 32
        # includes dk_refcnt(8) + metadata(8) + usable(8) + nentries(8)
        entries_start_offset = 32 + ix_total_size

        # is_unicode (stride 16) vs general (stride 24)
        # Empirical: kind 1 is Unicode Combined. kind 0 is General Combined.
        is_unicode = (dk_kind == 1)
        return entries_start_offset, ix_total_size, is_unicode, dk_kind != 0

    def _get_entry_stride(self, is_unicode: bool, is_split: bool) -> int:
        """Determine stride size for dictionary entries."""
        if is_split:
            return 16
        return 16 if is_unicode else 24

    def _read_dict_entry(
            self,
            entry_addr: int,
            stride: int,
            is_split: bool,
            values_array: Optional[ctypes._Pointer],
            index: int
    ) -> Tuple[Optional[int], Optional[int]]:
        """Read key and value pointers from a dictionary entry."""
        # Key pointer location depends on stride
        key_offset = 0 if stride == 16 else 8
        key_ptr = ctypes.c_void_p.from_address(entry_addr + key_offset).value

        # Value pointer location depends on split vs combined
        if is_split and values_array:
            val_ptr = values_array[index]
        else:
            val_offset = 8 if stride == 16 else 16
            val_ptr = ctypes.c_void_p.from_address(
                entry_addr + val_offset
            ).value

        return key_ptr, val_ptr

    def _examine_dict(self) -> None:
        """Examine dictionary internal structure using surgical Lens."""
        if (
            not self.lens
            or not isinstance(self.lens, DictLens)
            or not self.lens.ma_keys
        ):
            return

        keys_addr = self.lens.ma_keys
        keys_obj = DictKeysLens.from_address(keys_addr)

        values_ptr = self.lens.ma_values
        is_split = (values_ptr is not None)
        values_array = ctypes.cast(
            values_ptr,
            ctypes.POINTER(ctypes.c_void_p)
        ) if is_split else None

        keys_ptr = ctypes.cast(keys_addr, ctypes.POINTER(DictKeysLens))
        geom = self._get_dict_geometry(keys_ptr)
        entries_start_offset, _, is_unicode, _ = geom
        stride = self._get_entry_stride(is_unicode, is_split)

        print(
            f"\n[ DICT GEOMETRY: "
            f"{'UNICODE' if is_unicode else 'GENERAL'} | "
            f"{'SPLIT' if is_split else 'COMBINED'} ]"
        )

        print(
            f"  Keys: {hex(keys_addr)}"
            f" | Start: +{entries_start_offset}"
            f" | Stride: {stride}"
        )

        print("[ PARSED DENSE ENTRIES ]")

        dummy_ptr = _get_dummy_ptr()
        for i in range(keys_obj.dk_nentries):
            entry_addr = keys_addr + entries_start_offset + (i * stride)

            try:
                key_ptr, val_ptr = self._read_dict_entry(
                    entry_addr,
                    stride,
                    is_split,
                    values_array,
                    i
                )
                if key_ptr and key_ptr != dummy_ptr:
                    key = self.pull_data_from_address(key_ptr)
                    value = self.pull_data_from_address(
                        val_ptr
                    ) if val_ptr else "NULL"
                    print(f"  ▶ Slot {i} | Key: {key} | Val: {value}")
                elif key_ptr == dummy_ptr:
                    print(f"    Slot {i} | <Tombstone/Dummy>")
                else:
                    print(f"    Slot {i} | <Empty>")
            except Exception as e:
                print(f"    Slot {i} | Memory Error: {e}")

    def _examine_set(self) -> None:
        """Examine set internal hash table."""
        if not self.lens or not isinstance(self.lens, SetLens):
            return

        print("\n[ SET HASH TABLE ]")
        table_ptr = self.lens.table
        dummy_ptr = _get_dummy_ptr()

        for i in range(self.lens.mask + 1):
            entry = table_ptr[i]
            key_addr = entry.key
            if key_addr and key_addr != dummy_ptr:
                val = self.pull_data_from_address(key_addr)
                print(
                    f"  ▶ Bucket {i:2d}"
                    f" | Hash: {hex(entry.hash)}"
                    f" | Key: {val}"
                    )
            elif key_addr == dummy_ptr:
                print(f"    Bucket {i:2d} | <Dummy>")

    def _examine_tuple(self) -> None:
        """Examine tuple items from memory."""
        size = ctypes.c_ssize_t.from_address(self.address + 16).value
        # hash_cached(8) starts at +24, items start at +32
        items_array = ctypes.cast(
            self.address + 32,
            ctypes.POINTER(ctypes.c_void_p)
        )
        print("\n[ TUPLE ITEMS ]")
        for i in range(size):
            addr = items_array[i]
            val = self.pull_data_from_address(addr)
            print(f"  Item {i} | Addr: {hex(addr)} | Value: {val}")

    def _examine_list(self) -> None:
        """Display list contents using lens."""
        if not isinstance(self.lens, ListLens):
            return

        print("\n[ LIST CONTENTS (Follow Pointers) ]")
        for i in range(self.lens.ob_size):
            obj_addr = self.lens.ob_item[i]
            actual_value = self.pull_data_from_address(obj_addr)
            _, item_type_name = self._get_type_info(obj_addr)
            print(
                f"  Item {i}"
                f" | Addr: {hex(obj_addr)}"
                f" | {item_type_name.ljust(5)}: {actual_value}"
            )

    def dump_raw(
            self,
            addr: int,
            length: int = 64,
            label: str = "MEMORY"
    ) -> None:
        """Display hex dump of memory with ASCII representation."""
        print(f"\n--- DEBUG DUMP: {label} AT {hex(addr)} ---")

        try:
            raw_data = ctypes.string_at(addr, length)

            for i in range(0, length, 16):
                offset = f"+{i:03x}"
                chunk = raw_data[i:i+16]
                hex_vals = ' '.join(f"{b:02x}" for b in chunk).ljust(47)
                ascii_vals = "".join(
                    chr(b) if 32 <= b <= 126 else "." for b in chunk
                )
                print(f"{offset} | {hex_vals} | {ascii_vals}")

        except Exception as e:
            print(f"FAILED TO READ: {e}")
        print("-" * 60)

    def _print_logical_data(self) -> None:
        """Display logical field data from lens."""
        if not self.lens:
            return

        print("\n[ LOGICAL DATA ]")
        for field_info in getattr(self.lens, '_fields_', []):
            field_name = field_info[0]
            val = getattr(self.lens, field_name)
            is_ptr = isinstance(val, int) and field_name.endswith('_ptr')
            display_val = hex(val) if is_ptr else val
            print(f"  FIELD: {field_name.ljust(10)} | VALUE: {display_val}")

    def _print_raw_memory(self, raw_bytes: bytes, total_size: int) -> None:
        """Display raw memory dump in hex format."""
        print("\n[ RAW MEMORY DUMP ]")
        for i in range(0, total_size, 8):
            chunk = raw_bytes[i:i+8]
            marker = "<- DATA" if i == 16 else ""
            print(f"  +{i:02} | {chunk.hex(' ')} {marker}")

    def examine(self) -> None:
        """Comprehensive examination of Python object memory structure."""
        total_size = sys.getsizeof(self._target)
        # Avoid huge dumps for performance
        dump_size = min(total_size, 256)
        raw_bytes = ctypes.string_at(self.address, dump_size)

        print(f"\n{'='*60}")
        print(
            f"X-RAY AT: {hex(self.address)}"
            f" | TYPE: {self.type_name}"
            f" | SIZE: {total_size} bytes"
        )
        print(f"{'='*60}")

        print("[ HEADER ]")
        print(f"  +00 | ob_refcnt : {self.header.ob_refcnt}")
        print(f"  +08 | ob_type   : {hex(self.header.ob_type_ptr)}")

        # Type-specific examination
        dispatch = {
            'list': self._examine_list,
            'dict': self._examine_dict,
            'set': self._examine_set,
            'frozenset': self._examine_set,
            'tuple': self._examine_tuple,
        }

        if self.type_name in dispatch:
            dispatch[self.type_name]()

        self._print_logical_data()
        self._print_raw_memory(raw_bytes, dump_size)

        if total_size > 256:
            print("  ... (Memory dump truncated for display)")

        print(f"{'='*60}")
