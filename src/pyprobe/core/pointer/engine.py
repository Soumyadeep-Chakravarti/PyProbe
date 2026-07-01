"""PyProbe — Memory Inspector

High-speed memory introspection for CPython 3.14.
"""

import builtins
import ctypes
import importlib.util
import os
import sys
from typing import Any, Dict, List, Optional, Tuple, Type, Union, cast

from pyprobe.raw.headers.py_object import PyObjectHeader
from pyprobe.raw.headers.py_type import PyTypeObject
from pyprobe.raw.lenses.bytes_lens import BytesLens
from pyprobe.raw.lenses.dict_lens import DictKeysLens, DictLens
from pyprobe.raw.lenses.float_lens import FloatLens
import pyprobe.core.Scalpel as Scalpel
from pyprobe.core.common import PyProbeError
from pyprobe.raw.lenses.int_lens import IntLens
from pyprobe.raw.lenses.list_lens import ListLens
from pyprobe.raw.lenses.set_lens import SetLens
from pyprobe.raw.lenses.str_lens import CompactUnicodeLens, StringLens
from pyprobe.raw.lenses.tuple_lens import TupleLens

# ── NEW: Dynamic offset discovery (no hardcoding, no version checks) ──
from pyprobe.core.offset_discovery import (
    TUPLE_ITEMS_OFFSET,
    LIST_ITEMS_OFFSET,
    DICT_MA_KEYS_OFFSET,
)

# Type aliases
VisitedSet = set[int]
ExtractorFunc = Any  # Callable to extractor method

# PyObject_HEAD
HEADER_SIZE = 16


def _get_ring():
    """Lazy-load get_ring from log.py to avoid circular imports."""
    if "pyprobe.core.log" in sys.modules:
        return sys.modules["pyprobe.core.log"].get_ring()
    _log_path = os.path.join(os.path.dirname(__file__), "..", "log.py")
    _spec = importlib.util.spec_from_file_location("pyprobe.core.log", _log_path)
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules["pyprobe.core.log"] = _mod
    _spec.loader.exec_module(_mod)
    return _mod.get_ring()

# PyVarObject_HEAD
VAR_HEADER_SIZE = 24

# Industrial Singleton Discovery
_dummy_ptr_cache: Optional[int] = None


def _get_dummy_ptr() -> Optional[int]:
    """Resolve the address of the internal <dummy> singleton safely.

    The <dummy> singleton is used as a tombstone marker in CPython dicts
    and sets. This function locates it by creating a temporary dict with
    a deleted key and inspecting the memory layout.

    Returns:
        The memory address of the <dummy> singleton, or None if it
        could not be located (with a warning).
    """
    global _dummy_ptr_cache
    if _dummy_ptr_cache is None:
        try:
            d = {0: 0}
            del d[0]
            addr = id(d)
            if DICT_MA_KEYS_OFFSET is not None:
                keys_addr: Optional[int] = ctypes.c_void_p.from_address(
                    addr + DICT_MA_KEYS_OFFSET
                ).value
                if keys_addr is not None:
                    keys_lens = DictKeysLens.from_address(keys_addr)
                    dk_kind = keys_lens.dk_kind
                    is_unicode = dk_kind == 1
                    log2_ix = keys_lens.dk_log2_index_bytes
                    entries_start = 32 + (1 << log2_ix)
                    key_offset = 0 if is_unicode else 8
                    _dummy_ptr_cache = ctypes.c_void_p.from_address(
                        keys_addr + entries_start + key_offset
                    ).value
        except Exception as e:
            _get_ring().warn(3, f"Failed to locate <dummy> singleton: {e}. "
                "Dict/set tombstone detection may not work correctly.")
    return _dummy_ptr_cache


# Architecture Guard
if ctypes.sizeof(ctypes.c_void_p) != 8:
    raise PyProbeError("PyProbe currently only supports 64-bit CPython architectures.")

# Pre-compute the set of all builtin exception type names for dynamic matching
_EXCEPTION_NAMES: set[str] = set()
for _name in dir(builtins):
    _obj = getattr(builtins, _name, None)
    if isinstance(_obj, type) and issubclass(_obj, BaseException):
        _EXCEPTION_NAMES.add(_name)

# Container types that require visited-set tracking (frozen at module load)
_CONTAINER_NAMES: frozenset[str] = frozenset({
    "list", "tuple", "dict", "set", "frozenset", "range",
    "slice", "function", "module", "cell", "property",
    "staticmethod", "classmethod", "generator", "enumerate",
})

# Cached lookups for performance
_TYPE_NAME_CACHE: Dict[int, str] = {}


# Sentinel value for unset target parameter
_UNSET = object()


class Pointer:
    """Memory introspection pointer for CPython objects."""

    # Class-level extractor table (populated after class definition)
    # Uses unbound methods — bound at dispatch time via extractor(self, addr, ...)
    _EXTRACTORS: Dict[str, Any] = {}

    def __init__(self, target: Any = _UNSET, *, address: Optional[int] = None, safe: bool = True) -> None:
        has_target = target is not _UNSET
        has_address = address is not None

        if has_target and has_address:
            raise ValueError("Cannot specify both 'target' and 'address'")
        if not has_target and not has_address:
            raise ValueError("Must specify either 'target' or 'address'")

        self._target = target if has_target else None
        self._from_address = has_address
        self._safe = safe
        self.address: int = address if has_address else id(target)
        self.header = PyObjectHeader.from_address(self.address)

        type_struct = PyTypeObject.from_address(self.header.ob_type_ptr)
        self.type_name: str = type_struct.tp_name.decode("utf-8")

        self.header_size = 16
        self.data_addr: int = self.address + self.header_size

        self.lens = self._get_lens()

    def _extract_dict(
        self, addr: int, visited: Optional[VisitedSet] = None, depth: int = 0
    ) -> Dict[Any, Any]:
        """Extract dictionary items using surgical DictLens."""
        lens = DictLens.from_address(addr + HEADER_SIZE)
        if not lens.ma_keys:
            return {}

        base_addr_val = ctypes.cast(lens.ma_keys, ctypes.c_void_p).value
        if not base_addr_val:
            return {}

        values_ptr = lens.ma_values
        is_split = values_ptr is not None
        values_array: Optional[Any] = (
            ctypes.cast(values_ptr, ctypes.POINTER(ctypes.c_void_p))
            if is_split
            else None
        )

        keys_addr = lens.ma_keys
        keys_obj = DictKeysLens.from_address(keys_addr)

        keys_ptr: Any = ctypes.cast(keys_addr, ctypes.POINTER(DictKeysLens))
        entries_start_offset, _, is_unicode, _ = self._get_dict_geometry(keys_ptr)
        stride = self._get_entry_stride(is_unicode, is_split)

        result: Dict[Any, Any] = {}
        dummy_ptr = _get_dummy_ptr()
        for i in range(keys_obj.dk_nentries):
            entry_addr = keys_addr + entries_start_offset + (i * stride)
            try:
                key_ptr, val_ptr = self._read_dict_entry(
                    entry_addr, stride, is_split, values_array, i
                )
                if key_ptr and key_ptr != dummy_ptr:
                    key = self.pull_data_from_address(key_ptr, visited, depth + 1)
                    value = (
                        self.pull_data_from_address(val_ptr, visited, depth + 1)
                        if val_ptr
                        else None
                    )
                    result[key] = value
            except Exception as e:
                result[f"<error_slot_{i}>"] = str(e)
        return result

    def _get_lens(self) -> Optional[Any]:
        lenses: Dict[str, Type[Any]] = {
            "int": IntLens,
            "float": FloatLens,
            "list": ListLens,
            "str": StringLens,
            "dict": DictLens,
            "tuple": TupleLens,
            "bytes": BytesLens,
            "set": SetLens,
            "frozenset": SetLens,
        }
        cls = lenses.get(self.type_name)
        return cls.from_address(self.address + self.header_size) if cls else None

    def _normalize_address(self, addr: Union[int, ctypes.c_void_p]) -> Optional[int]:
        """Convert address to integer format."""
        actual_addr = addr.value if isinstance(addr, ctypes.c_void_p) else addr
        return actual_addr if actual_addr and actual_addr != 0 else None

    def _get_type_name(self, type_addr: int) -> str:
        """Cache type name lookup."""
        if type_addr not in _TYPE_NAME_CACHE:
            try:
                type_struct = PyTypeObject.from_address(type_addr)
                if not type_struct.tp_name:
                    return f"<Uninitialized Type @ {hex(type_addr)}>"
                operator = type_struct.tp_name
                _TYPE_NAME_CACHE[type_addr] = operator.decode("utf-8")
            except Exception:
                return f"<Invalid Type @ {hex(type_addr)}>"
        return _TYPE_NAME_CACHE[type_addr]

    def _get_type_info(self, addr: int) -> Tuple[Optional[PyObjectHeader], str]:
        """Extract header and cached type name from address with safety."""
        if addr < 0x1000 or addr & 0x7 != 0:
            return None, f"<Bad Address {hex(addr)}>"

        try:
            header = PyObjectHeader.from_address(addr)
            if header.ob_type_ptr & 0x07 != 0 or header.ob_type_ptr < 0x1000:
                return header, f"<Corrupt Type @ {hex(header.ob_type_ptr)}>"

            type_name = self._get_type_name(header.ob_type_ptr)
            return header, type_name
        except Exception:
            return None, f"<Read Error {hex(addr)}>"

    def _extract_int(self, addr: int) -> int:
        """Extract integer value (PyLongObject)."""
        tag = ctypes.c_ssize_t.from_address(addr + HEADER_SIZE).value
        size = tag >> 3
        if size == 0:
            return 0
        negative = (tag >> 1) & 0x01
        digits_array = ctypes.cast(addr + 24, ctypes.POINTER(ctypes.c_uint32))
        result = 0
        for i in range(size):
            result += digits_array[i] * (1 << (30 * i))
        return -result if negative else result

    def _extract_float(self, addr: int) -> float:
        """Extract float value using FloatLens."""
        return FloatLens.from_address(addr + HEADER_SIZE).ob_fval

    def _extract_string(self, addr: int) -> str:
        """Extract string value using StringLens abstractions."""
        lens = StringLens.from_address(addr + HEADER_SIZE)
        kind = lens.kind
        if not lens.compact:
            return f"<non-compact str @ {hex(addr)}>"

        if lens.ascii:
            data_offset = 16 + ctypes.sizeof(StringLens)
            encoding = "ascii"
        else:
            data_offset = 16 + ctypes.sizeof(CompactUnicodeLens)
            encoding = {1: "latin1", 2: "utf-16", 4: "utf-32"}.get(kind, "utf-8")

        try:
            char_size = 4 if kind == 4 else (2 if kind == 2 else 1)
            total_bytes = lens.length * char_size
            raw_data = ctypes.string_at(addr + data_offset, total_bytes)
            if char_size > 1:
                encoding += "-le" if sys.byteorder == "little" else "-be"
            return raw_data.decode(encoding)
        except Exception as e:
            return f"<Error decoding str: {e}>"

    def _extract_tuple(
        self, addr: int, visited: Optional[VisitedSet] = None, depth: int = 0
    ) -> tuple[Any, ...]:
        """Extract tuple items using dynamically discovered offset."""
        size = ctypes.c_ssize_t.from_address(addr + HEADER_SIZE).value
        # ── CHANGE 2: Use discovered offset instead of hardcoded VAR_HEADER_SIZE + 8 ──
        items_array = ctypes.cast(
            addr + TUPLE_ITEMS_OFFSET, ctypes.POINTER(ctypes.c_void_p)
        )
        return tuple(
            self.pull_data_from_address(items_array[i], visited, depth + 1)
            for i in range(size)
        )

    def _extract_list(
        self, addr: int, visited: Optional[VisitedSet] = None, depth: int = 0
    ) -> list[Any]:
        """Extract list items using dynamically discovered offset."""
        size = ctypes.c_ssize_t.from_address(addr + HEADER_SIZE).value
        # ── CHANGE 3: Use discovered offset instead of hardcoded HEADER_SIZE + 8 ──
        items_ptr = ctypes.c_void_p.from_address(addr + LIST_ITEMS_OFFSET).value
        if not items_ptr:
            return []
        items_array = ctypes.cast(items_ptr, ctypes.POINTER(ctypes.c_void_p))
        return [
            self.pull_data_from_address(items_array[i], visited, depth + 1)
            for i in range(size)
        ]

    def _extract_bytes(self, addr: int) -> bytes:
        """Extract bytes data structure."""
        size = ctypes.c_ssize_t.from_address(addr + HEADER_SIZE).value
        return ctypes.string_at(addr + VAR_HEADER_SIZE + 8, size)

    def _extract_set(
        self, addr: int, visited: Optional[VisitedSet] = None, depth: int = 0
    ) -> set[Any]:
        """Extract set using surgical lens — unchanged, already works."""
        lens = SetLens.from_address(addr + self.header_size)
        result: set[Any] = set()
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

    def _extract_bool(self, addr: int) -> bool:
        """Extract boolean value."""
        int_val = self._extract_int(addr)
        return bool(int_val)

    def _extract_none(self, addr: int) -> None:
        """Extract None singleton."""
        return None

    def _extract_complex(self, addr: int) -> complex:
        """Extract complex number."""
        real = ctypes.c_double.from_address(addr + HEADER_SIZE).value
        imag = ctypes.c_double.from_address(addr + HEADER_SIZE + 8).value
        return complex(real, imag)

    def _extract_range(
        self, addr: int, visited: Optional[VisitedSet] = None, depth: int = 0
    ) -> range:
        """Extract range object."""
        start_ptr: Optional[int] = ctypes.c_void_p.from_address(addr + HEADER_SIZE).value
        stop_ptr: Optional[int] = ctypes.c_void_p.from_address(addr + HEADER_SIZE + 8).value
        step_ptr: Optional[int] = ctypes.c_void_p.from_address(addr + HEADER_SIZE + 16).value
        start = self.pull_data_from_address(start_ptr or 0, visited, depth + 1) if start_ptr else 0
        stop = self.pull_data_from_address(stop_ptr or 0, visited, depth + 1) if stop_ptr else 0
        step = self.pull_data_from_address(step_ptr or 1, visited, depth + 1) if step_ptr else 1
        return range(start, stop, step)

    def _extract_slice(
        self, addr: int, visited: Optional[VisitedSet] = None, depth: int = 0
    ) -> slice:
        """Extract slice object."""
        start_ptr: Optional[int] = ctypes.c_void_p.from_address(addr + HEADER_SIZE).value
        stop_ptr: Optional[int] = ctypes.c_void_p.from_address(addr + HEADER_SIZE + 8).value
        step_ptr: Optional[int] = ctypes.c_void_p.from_address(addr + HEADER_SIZE + 16).value
        start = self.pull_data_from_address(start_ptr or 0, visited, depth + 1) if start_ptr else None
        stop = self.pull_data_from_address(stop_ptr or 0, visited, depth + 1) if stop_ptr else None
        step = self.pull_data_from_address(step_ptr or 0, visited, depth + 1) if step_ptr else None
        start = None if start == "NULL" else start
        stop = None if stop == "NULL" else stop
        step = None if step == "NULL" else step
        return slice(start, stop, step)

    def _extract_bytearray(self, addr: int) -> bytearray:
        """Extract bytearray data."""
        size = ctypes.c_ssize_t.from_address(addr + HEADER_SIZE).value
        ob_start = ctypes.c_void_p.from_address(addr + HEADER_SIZE + 24).value
        if not ob_start or size <= 0:
            return bytearray()
        data = ctypes.string_at(ob_start, size)
        return bytearray(data)

    def _extract_memoryview(self, addr: int) -> bytes:
        """Extract memoryview contents as bytes."""
        buf_ptr = ctypes.c_void_p.from_address(addr + 56).value
        length = ctypes.c_ssize_t.from_address(addr + 72).value
        if not buf_ptr or length <= 0:
            return b""
        return ctypes.string_at(buf_ptr, length)

    def _extract_function(
        self, addr: int, visited: Optional[VisitedSet] = None, depth: int = 0
    ) -> Dict[str, Any]:
        """Extract function object metadata."""
        result = {"__type__": "function"}
        name_ptr = ctypes.c_void_p.from_address(addr + 32).value
        if name_ptr:
            result["__name__"] = self.pull_data_from_address(name_ptr, visited, depth + 1)
        qualname_ptr = ctypes.c_void_p.from_address(addr + 40).value
        if qualname_ptr:
            result["__qualname__"] = self.pull_data_from_address(qualname_ptr, visited, depth + 1)
        defaults_ptr = ctypes.c_void_p.from_address(addr + 56).value
        if defaults_ptr:
            result["__defaults__"] = self.pull_data_from_address(defaults_ptr, visited, depth + 1)
        doc_ptr = ctypes.c_void_p.from_address(addr + 80).value
        if doc_ptr:
            result["__doc__"] = self.pull_data_from_address(doc_ptr, visited, depth + 1)
        module_ptr = ctypes.c_void_p.from_address(addr + 104).value
        if module_ptr:
            result["__module__"] = self.pull_data_from_address(module_ptr, visited, depth + 1)
        return result

    def _extract_type(self, addr: int) -> Dict[str, Any]:
        """Extract type object metadata."""
        result = {"__type__": "type"}
        try:
            tp_name_ptr = ctypes.c_char_p.from_address(addr + 24).value
            if tp_name_ptr:
                result["__name__"] = tp_name_ptr.decode("utf-8", errors="replace")
            else:
                result["__name__"] = "<unknown type>"
        except Exception as e:
            result["__name__"] = f"<error: {e}>"
        return result

    def _extract_module(
        self, addr: int, visited: Optional[VisitedSet] = None, depth: int = 0
    ) -> Dict[str, Any]:
        """Extract module object metadata."""
        result: Dict[str, Any] = {"__type__": "module"}
        try:
            dict_ptr = ctypes.c_void_p.from_address(addr + 16).value
            if dict_ptr:
                md_dict = self.pull_data_from_address(dict_ptr, visited, depth + 1)
                if isinstance(md_dict, dict):
                    md_dict_typed = cast(Dict[Any, Any], md_dict)
                    result["__name__"] = str(md_dict_typed.get("__name__", "<unknown>"))
                    result["__doc__"] = md_dict_typed.get("__doc__")
                    result["__file__"] = md_dict_typed.get("__file__")
                    keys: list[Any] = list(md_dict_typed.keys())
                    result["__dict_keys__"] = keys[:20]
                    if len(keys) > 20:
                        result["__dict_keys__"].append(f"... and {len(keys) - 20} more")
                else:
                    result["__name__"] = "<unknown>"
                    result["__dict_keys__"] = []
            else:
                result["__name__"] = "<no dict>"
                result["__dict_keys__"] = []
        except Exception as e:
            result["__name__"] = f"<error: {e}>"
            result["__dict_keys__"] = []
        return result

    def _extract_code(self, addr: int) -> Dict[str, Any]:
        """Extract code object metadata."""
        result = {"__type__": "code"}
        try:
            consts_ptr = ctypes.c_void_p.from_address(addr + 24).value
            filename_ptr = ctypes.c_void_p.from_address(addr + 112).value
            name_ptr = ctypes.c_void_p.from_address(addr + 120).value
            if name_ptr:
                result["co_name"] = self.pull_data_from_address(name_ptr)
            if filename_ptr:
                result["co_filename"] = self.pull_data_from_address(filename_ptr)
            if consts_ptr:
                result["co_consts"] = self.pull_data_from_address(consts_ptr)
        except Exception as e:
            result["error"] = str(e)
        return result

    def _extract_cell(
        self, addr: int, visited: Optional[VisitedSet] = None, depth: int = 0
    ) -> Dict[str, Any]:
        """Extract cell object."""
        result = {"__type__": "cell"}
        try:
            content_ptr = ctypes.c_void_p.from_address(addr + 16).value
            if content_ptr:
                result["cell_contents"] = self.pull_data_from_address(content_ptr, visited, depth + 1)
            else:
                result["cell_contents"] = "<empty cell>"
        except Exception as e:
            result["cell_contents"] = f"<error: {e}>"
        return result

    def _extract_exception(
        self, addr: int, visited: Optional[VisitedSet] = None, depth: int = 0
    ) -> Dict[str, Any]:
        """Extract exception object."""
        result: Dict[str, Any] = {"__type__": "exception"}
        try:
            _, type_name = self._get_type_info(addr)
            result["exception_type"] = type_name
            args_ptr = ctypes.c_void_p.from_address(addr + 24).value
            if args_ptr:
                result["args"] = self.pull_data_from_address(args_ptr, visited, depth + 1)
            else:
                result["args"] = tuple()
        except Exception as e:
            result["exception_type"] = "<unknown>"
            result["args"] = (f"<error extracting: {e}>",)
        return result

    def _extract_property(
        self, addr: int, visited: Optional[VisitedSet] = None, depth: int = 0
    ) -> Dict[str, Any]:
        """Extract property descriptor."""
        result = {"__type__": "property"}
        try:
            fget_ptr = ctypes.c_void_p.from_address(addr + 16).value
            fset_ptr = ctypes.c_void_p.from_address(addr + 24).value
            fdel_ptr = ctypes.c_void_p.from_address(addr + 32).value
            doc_ptr = ctypes.c_void_p.from_address(addr + 40).value
            if fget_ptr:
                result["fget"] = self.pull_data_from_address(fget_ptr, visited, depth + 1)
            if fset_ptr:
                result["fset"] = self.pull_data_from_address(fset_ptr, visited, depth + 1)
            if fdel_ptr:
                result["fdel"] = self.pull_data_from_address(fdel_ptr, visited, depth + 1)
            if doc_ptr:
                result["__doc__"] = self.pull_data_from_address(doc_ptr, visited, depth + 1)
        except Exception as e:
            result["error"] = str(e)
        return result

    def _extract_staticmethod(
        self, addr: int, visited: Optional[VisitedSet] = None, depth: int = 0
    ) -> Dict[str, Any]:
        """Extract staticmethod descriptor."""
        result = {"__type__": "staticmethod"}
        try:
            callable_ptr = ctypes.c_void_p.from_address(addr + 16).value
            if callable_ptr:
                result["__func__"] = self.pull_data_from_address(callable_ptr, visited, depth + 1)
        except Exception as e:
            result["error"] = str(e)
        return result

    def _extract_classmethod(
        self, addr: int, visited: Optional[VisitedSet] = None, depth: int = 0
    ) -> Dict[str, Any]:
        """Extract classmethod descriptor."""
        result = {"__type__": "classmethod"}
        try:
            callable_ptr = ctypes.c_void_p.from_address(addr + 16).value
            if callable_ptr:
                result["__func__"] = self.pull_data_from_address(callable_ptr, visited, depth + 1)
        except Exception as e:
            result["error"] = str(e)
        return result

    def _extract_builtin_function(self, addr: int) -> Dict[str, Any]:
        """Extract builtin_function_or_method object."""
        result = {"__type__": "builtin_function_or_method"}
        try:
            ml_ptr = ctypes.c_void_p.from_address(addr + 16).value
            if ml_ptr:
                name_ptr = ctypes.c_char_p.from_address(ml_ptr).value
                if name_ptr:
                    result["__name__"] = name_ptr.decode("utf-8", errors="replace")
                else:
                    result["__name__"] = "<unknown>"
            else:
                result["__name__"] = "<no method def>"
        except Exception as e:
            result["__name__"] = f"<error: {e}>"
        return result

    def _extract_generator(
        self, addr: int, visited: Optional[VisitedSet] = None, depth: int = 0
    ) -> Dict[str, Any]:
        """Extract generator object metadata."""
        result = {"__type__": "generator"}
        result["status"] = "generator object (state not fully extracted)"
        return result

    def _extract_enumerate(
        self, addr: int, visited: Optional[VisitedSet] = None, depth: int = 0
    ) -> Dict[str, Any]:
        """Extract enumerate object."""
        result: Dict[str, Any] = {"__type__": "enumerate"}
        try:
            index = ctypes.c_ssize_t.from_address(addr + 16).value
            result["start_index"] = int(index)
        except Exception as e:
            result["start_index"] = f"<error: {e}>"
        return result

    def pull_data_from_address(
        self,
        addr: Union[int, ctypes.c_void_p],
        visited: Optional[VisitedSet] = None,
        depth: int = 0,
    ) -> Any:
        """Extract Python object data from memory address."""
        actual_addr = self._normalize_address(addr)
        if actual_addr is None:
            return "NULL"

        if visited is None:
            visited = set()

        if actual_addr in visited:
            return f"<Cycle @ {hex(actual_addr)}>"

        if depth > 100:
            return f"<Max Depth @ {hex(actual_addr)}>"

        try:
            _, type_name = self._get_type_info(actual_addr)

            is_container = type_name in _CONTAINER_NAMES
            is_exception = type_name in _EXCEPTION_NAMES
            if is_container or is_exception:
                visited.add(actual_addr)

            extractor = self._EXTRACTORS.get(type_name)
            if extractor:
                if is_container or is_exception:
                    return extractor(self, actual_addr, visited, depth)
                return extractor(self, actual_addr)

            return f"<{type_name} @ {hex(actual_addr)}>"
        except Exception as e:
            return f"<Error reading {hex(actual_addr)}: {e}>"

    def xray(self) -> Any:
        """Extract the logical Python value from the pinned object's memory."""
        return self.pull_data_from_address(self.address)

    def mutate_float(self, target_slot_addr: int, new_val: float) -> None:
        """Mutate a float at a given address."""
        if self._target is not None and isinstance(self._target, float):
            Scalpel.mutate_float(self._target, new_val, safe=self._safe)
        else:
            raise PyProbeError(
                "Pointer.mutate_float requires a Python float object. "
                "Use Scalpel.mutate_float with a Python float object instead."
            )

    def mutate_int(self, target_addr: int, new_val: int) -> None:
        """Mutate a small int at a given address."""
        if self._target is not None and isinstance(self._target, int):
            Scalpel.mutate_int(self._target, new_val, safe=self._safe)
        else:
            raise PyProbeError(
                "Pointer.mutate_int requires a Python int object. "
                "Use Scalpel.mutate_int with a Python int object instead."
            )

    def safe_list_swap(self, target_list: list[Any], index: int, new_obj: Any) -> None:
        """Swap a list item by hot-swapping the memory pointer."""
        Scalpel.safe_list_swap(target_list, index, new_obj, safe=self._safe)

    def safe_dict_value_swap(self, target_dict: dict[Any, Any], key: Any, new_value: Any) -> None:
        """Swap a dict value pointer."""
        Scalpel.safe_dict_value_swap(target_dict, key, new_value, safe=self._safe)

    def mutate_batch(
        self,
        operations: list[tuple],
        safe: Optional[bool] = None,
    ) -> None:
        """Execute multiple mutations atomically — all rolled back on failure."""
        Scalpel.mutate_batch(operations, safe=self._safe if safe is None else safe)

    def __repr__(self) -> str:
        """Return a developer-friendly representation of the Pointer."""
        target_info = (
            f"target={self._target!r}"
            if not self._from_address
            else f"address={hex(self.address)}"
        )
        return (
            f"<Pointer({target_info}) type={self.type_name!r} at {hex(self.address)}>"
        )

    def _get_dict_geometry(
        self, keys_ptr: Any
    ) -> Tuple[int, int, bool, bool]:
        """Calculate dictionary memory layout parameters using DictKeysLens."""
        keys = keys_ptr.contents
        dk_kind = keys.dk_kind
        log2_ix_total = keys.dk_log2_index_bytes
        ix_total_size = 1 << log2_ix_total
        entries_start_offset = 32 + ix_total_size
        is_unicode = dk_kind == 1
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
        values_array: Optional[Any],
        index: int,
    ) -> Tuple[Optional[int], Optional[int]]:
        """Read key and value pointers from a dictionary entry."""
        key_offset = 0 if stride == 16 else 8
        key_ptr = ctypes.c_void_p.from_address(entry_addr + key_offset).value

        if is_split and values_array:
            val_ptr = values_array[index]
        else:
            val_offset = 8 if stride == 16 else 16
            val_ptr = ctypes.c_void_p.from_address(entry_addr + val_offset).value

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
        is_split = values_ptr is not None
        values_array = (
            ctypes.cast(values_ptr + 8, ctypes.POINTER(ctypes.c_void_p))
            if is_split
            else None
        )

        keys_ptr = ctypes.cast(keys_addr, ctypes.POINTER(DictKeysLens))
        geom = self._get_dict_geometry(keys_ptr)
        entries_start_offset, _, is_unicode, _ = geom
        stride = self._get_entry_stride(is_unicode, is_split)

        ring = _get_ring()
        ring.debug(3, f"  dict: {'UNICODE' if is_unicode else 'GENERAL'} "
            f"{'SPLIT' if is_split else 'COMBINED'}"
            f"  keys={hex(keys_addr)}  start=+{entries_start_offset}  stride={stride}")

        dummy_ptr = _get_dummy_ptr()
        for i in range(keys_obj.dk_nentries):
            entry_addr = keys_addr + entries_start_offset + (i * stride)
            try:
                key_ptr, val_ptr = self._read_dict_entry(
                    entry_addr, stride, is_split, values_array, i
                )
                if key_ptr and key_ptr != dummy_ptr:
                    key = self.pull_data_from_address(key_ptr)
                    value = self.pull_data_from_address(val_ptr) if val_ptr else "NULL"
                    ring.debug(3, f"    [{i}] {key!r} = {value}")
                elif key_ptr == dummy_ptr:
                    ring.debug(3, f"    [{i}] <tombstone>")
                else:
                    ring.debug(3, f"    [{i}] <empty>")
            except Exception as e:
                ring.debug(3, f"    [{i}] <error: {e}>")

    def _examine_set(self) -> None:
        """Examine set internal hash table."""
        if not self.lens or not isinstance(self.lens, SetLens):
            return

        table_ptr = self.lens.table
        dummy_ptr = _get_dummy_ptr()

        ring = _get_ring()
        ring.debug(3, f"  set: mask={self.lens.mask}")
        for i in range(self.lens.mask + 1):
            entry = table_ptr[i]
            key_addr = entry.key
            if key_addr and key_addr != dummy_ptr:
                val = self.pull_data_from_address(key_addr)
                ring.debug(3, f"    [{i:2d}] hash={hex(entry.hash)} key={val!r}")
            elif key_addr == dummy_ptr:
                ring.debug(3, f"    [{i:2d}] <dummy>")

    def _examine_tuple(self) -> None:
        """Examine tuple items using dynamically discovered offset."""
        ring = _get_ring()
        size = ctypes.c_ssize_t.from_address(self.address + HEADER_SIZE).value
        items_array = ctypes.cast(
            self.address + TUPLE_ITEMS_OFFSET, ctypes.POINTER(ctypes.c_void_p)
        )
        ring.debug(3, f"  tuple: size={size}")
        for i in range(size):
            addr = items_array[i]
            val = self.pull_data_from_address(addr)
            ring.debug(3, f"    [{i}] {val!r}")

    def _examine_list(self) -> None:
        """Display list contents using dynamically discovered offset."""
        if not isinstance(self.lens, ListLens):
            return

        items_ptr = ctypes.c_void_p.from_address(
            self.address + LIST_ITEMS_OFFSET
        ).value
        if not items_ptr:
            return
        items_array = ctypes.cast(items_ptr, ctypes.POINTER(ctypes.c_void_p))

        ring = _get_ring()
        ring.debug(3, f"  list: size={self.lens.ob_size}")
        for i in range(self.lens.ob_size):
            obj_addr = items_array[i]
            actual_value = self.pull_data_from_address(obj_addr)
            ring.debug(3, f"    [{i}] {actual_value!r}")

    def dump_raw(self, addr: int, length: int = 64, label: str = "MEMORY") -> None:
        """Display hex dump of memory with ASCII representation."""
        ring = _get_ring()
        ring.debug(3, f"--- DEBUG DUMP: {label} AT {hex(addr)} ---")
        try:
            raw_data = ctypes.string_at(addr, length)
            for i in range(0, length, 16):
                offset = f"+{i:03x}"
                chunk = raw_data[i : i + 16]
                hex_vals = " ".join(f"{b:02x}" for b in chunk).ljust(47)
                ascii_vals = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
                ring.debug(3, f"{offset} | {hex_vals} | {ascii_vals}")
        except Exception as e:
            ring.debug(3, f"FAILED TO READ: {e}")
        ring.debug(3, "-" * 60)

    def _print_logical_data(self) -> None:
        """Display logical field data from lens."""
        if not self.lens:
            return

        ring = _get_ring()
        ring.debug(3, "  fields:")
        for field_info in getattr(self.lens, "_fields_", []):
            field_name = field_info[0]
            val = getattr(self.lens, field_name)
            if hasattr(val, "_type_"):
                continue
            is_ptr = isinstance(val, int) and field_name.endswith("_ptr")
            display_val = hex(val) if is_ptr else val
            ring.debug(3, f"    {field_name} = {display_val}")

    def _print_raw_memory(self, raw_bytes: bytes, total_size: int) -> None:
        """Display raw memory dump in hex format."""
        ring = _get_ring()
        ring.debug(3, "  hex:")
        for i in range(0, total_size, 16):
            chunk = raw_bytes[i : i + 16]
            ring.debug(3, f"    {i:04x} {chunk.hex(' ')}")

    def examine(self) -> None:
        """Comprehensive examination of Python object memory structure."""
        ring = _get_ring()
        total_size = sys.getsizeof(self._target)
        dump_size = min(total_size, 64)
        raw_bytes = ctypes.string_at(self.address, dump_size)

        ring.debug(3, f"X-RAY {hex(self.address)} type={self.type_name} size={total_size}B")
        ring.debug(3, f"  refcnt={self.header.ob_refcnt}  type_ptr={hex(self.header.ob_type_ptr)}")

        dispatch = {
            "list": self._examine_list,
            "dict": self._examine_dict,
            "set": self._examine_set,
            "frozenset": self._examine_set,
            "tuple": self._examine_tuple,
        }

        if self.type_name in dispatch:
            dispatch[self.type_name]()

        self._print_logical_data()
        self._print_raw_memory(raw_bytes, dump_size)


# ── Populate class-level extractor table (after class definition) ──────────
Pointer._EXTRACTORS = {
    "int": Pointer._extract_int,
    "float": Pointer._extract_float,
    "complex": Pointer._extract_complex,
    "str": Pointer._extract_string,
    "tuple": Pointer._extract_tuple,
    "list": Pointer._extract_list,
    "dict": Pointer._extract_dict,
    "bytes": Pointer._extract_bytes,
    "bytearray": Pointer._extract_bytearray,
    "memoryview": Pointer._extract_memoryview,
    "set": Pointer._extract_set,
    "frozenset": Pointer._extract_set,
    "bool": Pointer._extract_bool,
    "NoneType": Pointer._extract_none,
    "range": Pointer._extract_range,
    "slice": Pointer._extract_slice,
    "function": Pointer._extract_function,
    "type": Pointer._extract_type,
    "module": Pointer._extract_module,
    "code": Pointer._extract_code,
    "cell": Pointer._extract_cell,
    "property": Pointer._extract_property,
    "staticmethod": Pointer._extract_staticmethod,
    "classmethod": Pointer._extract_classmethod,
    "builtin_function_or_method": Pointer._extract_builtin_function,
    "generator": Pointer._extract_generator,
    "enumerate": Pointer._extract_enumerate,
    "BaseException": Pointer._extract_exception,
    "Exception": Pointer._extract_exception,
    "StopIteration": Pointer._extract_exception,
    "ArithmeticError": Pointer._extract_exception,
    "AssertionError": Pointer._extract_exception,
    "AttributeError": Pointer._extract_exception,
    "BlockingIOError": Pointer._extract_exception,
    "BrokenPipeError": Pointer._extract_exception,
    "ConnectionError": Pointer._extract_exception,
    "EOFError": Pointer._extract_exception,
    "FileExistsError": Pointer._extract_exception,
    "FileNotFoundError": Pointer._extract_exception,
    "FloatingPointError": Pointer._extract_exception,
    "GeneratorExit": Pointer._extract_exception,
    "IOError": Pointer._extract_exception,
    "ImportError": Pointer._extract_exception,
    "IndentationError": Pointer._extract_exception,
    "IndexError": Pointer._extract_exception,
    "IsADirectoryError": Pointer._extract_exception,
    "KeyError": Pointer._extract_exception,
    "LookupError": Pointer._extract_exception,
    "MemoryError": Pointer._extract_exception,
    "ModuleNotFoundError": Pointer._extract_exception,
    "NameError": Pointer._extract_exception,
    "NotADirectoryError": Pointer._extract_exception,
    "NotImplementedError": Pointer._extract_exception,
    "OSError": Pointer._extract_exception,
    "OverflowError": Pointer._extract_exception,
    "PermissionError": Pointer._extract_exception,
    "ProcessLookupError": Pointer._extract_exception,
    "RecursionError": Pointer._extract_exception,
    "ReferenceError": Pointer._extract_exception,
    "RuntimeError": Pointer._extract_exception,
    "SyntaxError": Pointer._extract_exception,
    "SystemError": Pointer._extract_exception,
    "SystemExit": Pointer._extract_exception,
    "TabError": Pointer._extract_exception,
    "TimeoutError": Pointer._extract_exception,
    "TypeError": Pointer._extract_exception,
    "UnboundLocalError": Pointer._extract_exception,
    "UnicodeDecodeError": Pointer._extract_exception,
    "UnicodeEncodeError": Pointer._extract_exception,
    "UnicodeError": Pointer._extract_exception,
    "UnicodeTranslateError": Pointer._extract_exception,
    "ValueError": Pointer._extract_exception,
    "ZeroDivisionError": Pointer._extract_exception,
}
