"""PyProbe Engine: High-speed memory introspection for CPython 3.14."""

import ctypes
import sys
import warnings
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
    """Resolve the address of the internal <dummy> singleton safely.

    The <dummy> singleton is used as a tombstone marker in CPython dicts
    and sets. This function locates it by creating a temporary dict with
    a deleted key and inspecting the memory layout.

    Returns:
        The memory address of the <dummy> singleton, or None if it
        could not be located (with a warning).
    """
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
        except Exception as e:
            warnings.warn(
                f"Failed to locate <dummy> singleton: {e}. "
                "Dict/set tombstone detection may not work correctly.",
                RuntimeWarning,
                stacklevel=2,
            )
    return _DUMMY_PTR


# Architecture Guard
if ctypes.sizeof(ctypes.c_void_p) != 8:
    raise RuntimeError("PyProbe currently only supports 64-bit CPython architectures.")

# Cached lookups for performance
_TYPE_NAME_CACHE: Dict[int, str] = {}


# Sentinel value for unset target parameter
_UNSET = object()


class Pointer:
    """Memory introspection pointer for CPython objects.

    A Pointer wraps a Python object and provides low-level access to its
    memory representation. It can be initialized either with a target object
    or with a raw memory address.

    Attributes:
        address: The memory address of the pinned object.
        type_name: The type name of the object at the address.
        header: The PyObjectHeader structure at the address.
        lens: A type-specific lens view of the object body (if available).
    """

    def __init__(self, target: Any = _UNSET, *, address: Optional[int] = None) -> None:
        """Initialize a Pointer to a Python object.

        Args:
            target: The Python object to pin. Mutually exclusive with address.
            address: A raw memory address to inspect.
                     Mutually exclusive with target.

        Raises:
            ValueError: If neither target nor address is provided, or both are.
        """
        has_target = target is not _UNSET
        has_address = address is not None

        if has_target and has_address:
            raise ValueError("Cannot specify both 'target' and 'address'")
        if not has_target and not has_address:
            raise ValueError("Must specify either 'target' or 'address'")

        self._target = target if has_target else None
        self._from_address = has_address
        self.address: int = address if has_address else id(target)
        self.header = PyObjectHeader.from_address(self.address)

        type_struct = PyTypeObject.from_address(self.header.ob_type_ptr)
        self.type_name: str = type_struct.tp_name.decode("utf-8")

        # Standard PyObject_HEAD is 16 bytes. All unique data starts at +16.
        self.header_size = 16
        self.data_addr: int = self.address + self.header_size

        # Dispatcher for data extraction
        self._extractors = {
            "int": self._extract_int,
            "float": self._extract_float,
            "complex": self._extract_complex,
            "str": self._extract_string,
            "tuple": self._extract_tuple,
            "list": self._extract_list,
            "dict": self._extract_dict,
            "bytes": self._extract_bytes,
            "bytearray": self._extract_bytearray,
            "memoryview": self._extract_memoryview,
            "set": self._extract_set,
            "frozenset": self._extract_set,
            "bool": self._extract_bool,
            "NoneType": self._extract_none,
            "range": self._extract_range,
            "slice": self._extract_slice,
            "function": self._extract_function,
            # New extractors
            "type": self._extract_type,
            "module": self._extract_module,
            "code": self._extract_code,
            "cell": self._extract_cell,
            "property": self._extract_property,
            "staticmethod": self._extract_staticmethod,
            "classmethod": self._extract_classmethod,
            "builtin_function_or_method": self._extract_builtin_function,
            "generator": self._extract_generator,
            "enumerate": self._extract_enumerate,
            # Exception types - map common ones to exception extractor
            "BaseException": self._extract_exception,
            "Exception": self._extract_exception,
            "ValueError": self._extract_exception,
            "TypeError": self._extract_exception,
            "KeyError": self._extract_exception,
            "IndexError": self._extract_exception,
            "AttributeError": self._extract_exception,
            "RuntimeError": self._extract_exception,
            "StopIteration": self._extract_exception,
            "OSError": self._extract_exception,
            "ImportError": self._extract_exception,
            "NameError": self._extract_exception,
            "ZeroDivisionError": self._extract_exception,
            # OSError subclasses
            "FileNotFoundError": self._extract_exception,
            "FileExistsError": self._extract_exception,
            "PermissionError": self._extract_exception,
            "IsADirectoryError": self._extract_exception,
            "NotADirectoryError": self._extract_exception,
            "TimeoutError": self._extract_exception,
            "ConnectionError": self._extract_exception,
            "BrokenPipeError": self._extract_exception,
            # Other common exceptions
            "AssertionError": self._extract_exception,
            "LookupError": self._extract_exception,
            "SyntaxError": self._extract_exception,
            "ModuleNotFoundError": self._extract_exception,
            "UnboundLocalError": self._extract_exception,
            "RecursionError": self._extract_exception,
        }

        self.lens = self._get_lens()

    def _extract_dict(
        self, addr: int, visited: Optional[set] = None, depth: int = 0
    ) -> dict:
        """Extract dictionary items using surgical DictLens."""
        # PyDictObject is NOT a VarObject, lens starts after PyObject_HEAD
        lens = DictLens.from_address(addr + HEADER_SIZE)
        if not lens.ma_keys:
            return {}

        base_addr_val = ctypes.cast(lens.ma_keys, ctypes.c_void_p).value
        if not base_addr_val:
            return {}

        values_ptr = lens.ma_values
        is_split = values_ptr is not None
        values_array = (
            ctypes.cast(values_ptr, ctypes.POINTER(ctypes.c_void_p))
            if is_split
            else None
        )

        keys_addr = lens.ma_keys
        keys_obj = DictKeysLens.from_address(keys_addr)

        entries_start_offset, _, is_unicode, _ = self._get_dict_geometry(
            ctypes.cast(keys_addr, ctypes.POINTER(DictKeysLens))
        )
        stride = self._get_entry_stride(is_unicode, is_split)

        result = {}
        dummy_ptr = _get_dummy_ptr()
        for i in range(keys_obj.dk_nentries):
            entry_addr = keys_addr + entries_start_offset + (i * stride)
            try:
                key_ptr, val_ptr = self._read_dict_entry(
                    entry_addr, stride, is_split, values_array, i
                )
                # Skip NULL and Dummy keys
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
        # Surgical views of the object body (look past the header)
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
        # Surgical grab uses the detected header size
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
                # tp_name is a pointer to a string.
                # We should check if it's readable.
                # Heuristic: tp_name should be > 0.
                if not type_struct.tp_name:
                    return f"<Uninitialized Type @ {hex(type_addr)}>"
                operator = type_struct.tp_name
                _TYPE_NAME_CACHE[type_addr] = operator.decode("utf-8")
            except Exception:
                return f"<Invalid Type @ {hex(type_addr)}>"
        return _TYPE_NAME_CACHE[type_addr]

    def _get_type_info(self, addr: int) -> Tuple[Optional[PyObjectHeader], str]:
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
        tag = ctypes.c_size_t.from_address(addr + HEADER_SIZE).value

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
        return FloatLens.from_address(addr + HEADER_SIZE).ob_fval

    def _extract_string(self, addr: int) -> str:
        """Extract string value using StringLens abstractions."""
        # Standard lens starts right after PyObject_HEAD (offset 16)
        lens = StringLens.from_address(addr + HEADER_SIZE)

        kind = lens.kind
        if not lens.compact:
            return f"<non-compact str @ {hex(addr)}>"

        if lens.ascii:
            # Data starts after ASCIIObject (prefix fields only)
            # ASCIIObject body size (excluding head) is usually 32
            # 16(HEAD) + 32(LENS) = 48.
            data_offset = 16 + ctypes.sizeof(StringLens)
            encoding = "ascii"
        else:
            # CompactUnicodeObject body size
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
        self, addr: int, visited: Optional[set] = None, depth: int = 0
    ) -> tuple:
        """Extract tuple items with cached hash offset (3.12+ layout)."""
        size = ctypes.c_ssize_t.from_address(addr + HEADER_SIZE).value
        # hash_cached(8) starts at +24, items start at +32
        items_array = ctypes.cast(
            addr + VAR_HEADER_SIZE + 8, ctypes.POINTER(ctypes.c_void_p)
        )
        return tuple(
            self.pull_data_from_address(items_array[i], visited, depth + 1)
            for i in range(size)
        )

    def _extract_list(
        self, addr: int, visited: Optional[set] = None, depth: int = 0
    ) -> list:
        """Extract list items using surgical offset."""
        size = ctypes.c_ssize_t.from_address(addr + HEADER_SIZE).value
        # Pointer to item array is at +24 (HEADER_SIZE + 8)
        items_ptr = ctypes.c_void_p.from_address(addr + HEADER_SIZE + 8).value
        if not items_ptr:
            return []
        items_array = ctypes.cast(items_ptr, ctypes.POINTER(ctypes.c_void_p))
        return [
            self.pull_data_from_address(items_array[i], visited, depth + 1)
            for i in range(size)
        ]

    def _extract_bytes(self, addr: int) -> bytes:
        """Extract bytes data structure (after PyVarObject_HEAD)."""
        # ob_size at HEADER_SIZE (offset 16)
        size = ctypes.c_ssize_t.from_address(addr + HEADER_SIZE).value
        # hash (8) + data (inline)
        # data starts at +32 (VAR_HEADER_SIZE + 8 for hash)
        return ctypes.string_at(addr + VAR_HEADER_SIZE + 8, size)

    def _extract_set(
        self, addr: int, visited: Optional[set] = None, depth: int = 0
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

    def _extract_bool(self, addr: int) -> bool:
        """Extract boolean value (bool inherits from int in CPython)."""
        # Bool uses the same layout as int - extract as int and convert
        int_val = self._extract_int(addr)
        return bool(int_val)

    def _extract_none(self, addr: int) -> None:
        """Extract None singleton."""
        # None is a singleton with no data payload - just return None
        return None

    def _extract_complex(self, addr: int) -> complex:
        """Extract complex number (two doubles after header)."""
        # PyComplexObject: real at +16, imag at +24
        real = ctypes.c_double.from_address(addr + HEADER_SIZE).value
        imag = ctypes.c_double.from_address(addr + HEADER_SIZE + 8).value
        return complex(real, imag)

    def _extract_range(
        self, addr: int, visited: Optional[set] = None, depth: int = 0
    ) -> range:
        """Extract range object (start, stop, step pointers)."""
        # PyRangeObject: start at +16, stop at +24, step at +32
        start_ptr = ctypes.c_void_p.from_address(addr + HEADER_SIZE).value
        stop_ptr = ctypes.c_void_p.from_address(addr + HEADER_SIZE + 8).value
        step_ptr = ctypes.c_void_p.from_address(addr + HEADER_SIZE + 16).value

        start = self.pull_data_from_address(start_ptr, visited, depth + 1)
        stop = self.pull_data_from_address(stop_ptr, visited, depth + 1)
        step = self.pull_data_from_address(step_ptr, visited, depth + 1)

        return range(start, stop, step)

    def _extract_slice(
        self, addr: int, visited: Optional[set] = None, depth: int = 0
    ) -> slice:
        """Extract slice object (start, stop, step pointers)."""
        # PySliceObject: start at +16, stop at +24, step at +32
        start_ptr = ctypes.c_void_p.from_address(addr + HEADER_SIZE).value
        stop_ptr = ctypes.c_void_p.from_address(addr + HEADER_SIZE + 8).value
        step_ptr = ctypes.c_void_p.from_address(addr + HEADER_SIZE + 16).value

        start = self.pull_data_from_address(start_ptr, visited, depth + 1)
        stop = self.pull_data_from_address(stop_ptr, visited, depth + 1)
        step = self.pull_data_from_address(step_ptr, visited, depth + 1)

        # Handle "NULL" sentinel for None values
        start = None if start == "NULL" else start
        stop = None if stop == "NULL" else stop
        step = None if step == "NULL" else step

        return slice(start, stop, step)

    def _extract_bytearray(self, addr: int) -> bytearray:
        """Extract bytearray data (variable-size mutable bytes)."""
        # PyByteArrayObject layout in 3.14:
        # +16: ob_size (logical size)
        # +24: ob_alloc (allocated size)
        # +32: ob_bytes (pointer to buffer)
        # +40: ob_start (start of logical data)
        size = ctypes.c_ssize_t.from_address(addr + HEADER_SIZE).value
        ob_start = ctypes.c_void_p.from_address(addr + HEADER_SIZE + 24).value

        if not ob_start or size <= 0:
            return bytearray()

        data = ctypes.string_at(ob_start, size)
        return bytearray(data)

    def _extract_memoryview(self, addr: int) -> bytes:
        """Extract memoryview contents as bytes.

        Note: Returns the raw bytes from the buffer. The actual memoryview
        object cannot be reconstructed since it requires a live buffer.
        """
        # PyMemoryViewObject layout in 3.14:
        # +16: hash
        # +24: mbuf (managed buffer)
        # +32: exports
        # +40-55: flags and other fields
        # +56: view.buf (pointer to actual data)
        # +64: view.obj (source object)
        # +72: view.len
        buf_ptr = ctypes.c_void_p.from_address(addr + 56).value
        length = ctypes.c_ssize_t.from_address(addr + 72).value

        if not buf_ptr or length <= 0:
            return b""

        return ctypes.string_at(buf_ptr, length)

    def _extract_function(
        self, addr: int, visited: Optional[set] = None, depth: int = 0
    ) -> dict:
        """Extract function object metadata.

        Returns a dict with function name, qualname, defaults, and annotations.
        Note: Cannot fully reconstruct the function, but provides introspection.
        """
        # PyFunctionObject layout in 3.14:
        # +16: func_globals (dict)
        # +24: func_builtins (dict)
        # +32: func_name (str)
        # +40: func_qualname (str)
        # +48: func_code (code object)
        # +56: func_defaults (tuple or NULL)
        # +64: func_kwdefaults (dict or NULL)
        # +72: func_closure (tuple or NULL)
        # +80: func_doc (str or NULL)
        # +88: func_dict (__dict__)
        # +96: func_weakreflist
        # +104: func_module
        # +112: func_annotations
        # +120: func_typeparams

        result = {"__type__": "function"}

        # Extract func_name
        name_ptr = ctypes.c_void_p.from_address(addr + 32).value
        if name_ptr:
            result["__name__"] = self.pull_data_from_address(
                name_ptr, visited, depth + 1
            )

        # Extract func_qualname
        qualname_ptr = ctypes.c_void_p.from_address(addr + 40).value
        if qualname_ptr:
            result["__qualname__"] = self.pull_data_from_address(
                qualname_ptr, visited, depth + 1
            )

        # Extract func_defaults
        defaults_ptr = ctypes.c_void_p.from_address(addr + 56).value
        if defaults_ptr:
            result["__defaults__"] = self.pull_data_from_address(
                defaults_ptr, visited, depth + 1
            )

        # Extract func_doc
        doc_ptr = ctypes.c_void_p.from_address(addr + 80).value
        if doc_ptr:
            result["__doc__"] = self.pull_data_from_address(doc_ptr, visited, depth + 1)

        # Extract func_module
        module_ptr = ctypes.c_void_p.from_address(addr + 104).value
        if module_ptr:
            result["__module__"] = self.pull_data_from_address(
                module_ptr, visited, depth + 1
            )

        return result

    def _extract_type(self, addr: int) -> dict:
        """Extract type object metadata.

        Extracts the type name from a PyTypeObject at the given address.

        Args:
            addr: Memory address of the type object.

        Returns:
            A dict containing:
                - __type__: Always "type"
                - __name__: The type's name (e.g., "int", "str", "MyClass")

        Note:
            Type objects have complex layouts; this extracts only the name
            to avoid potential issues with internal type flags and slots.
        """
        result = {"__type__": "type"}

        try:
            # PyTypeObject layout:
            # +24: tp_name (char*)
            tp_name_ptr = ctypes.c_char_p.from_address(addr + 24).value
            if tp_name_ptr:
                result["__name__"] = tp_name_ptr.decode("utf-8", errors="replace")
            else:
                result["__name__"] = "<unknown type>"
        except Exception as e:
            result["__name__"] = f"<error: {e}>"

        return result

    def _extract_module(
        self, addr: int, visited: Optional[set] = None, depth: int = 0
    ) -> dict:
        """Extract module object metadata.

        Extracts key module attributes including name, doc, file, and a
        subset of __dict__ keys.

        Args:
            addr: Memory address of the module object.
            visited: Set of visited addresses for cycle detection.
            depth: Current recursion depth.

        Returns:
            A dict containing:
                - __type__: Always "module"
                - __name__: Module name (e.g., "sys", "os")
                - __doc__: Module docstring (may be None)
                - __file__: Module file path (may be None for builtins)
                - __dict_keys__: First 20 keys from module's __dict__

        Note:
            Only the first 20 __dict__ keys are included to avoid
            excessive output for large modules.
        """
        result = {"__type__": "module"}

        try:
            # PyModuleObject layout:
            # +16: md_dict (__dict__)
            dict_ptr = ctypes.c_void_p.from_address(addr + 16).value
            if dict_ptr:
                # Extract dict but limit to just keys to avoid huge recursion
                md_dict = self.pull_data_from_address(dict_ptr, visited, depth + 1)
                if isinstance(md_dict, dict):
                    result["__name__"] = md_dict.get("__name__", "<unknown>")
                    result["__doc__"] = md_dict.get("__doc__")
                    result["__file__"] = md_dict.get("__file__")
                    # Don't include full __dict__ - too large
                    keys = list(md_dict.keys())
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

    def _extract_code(self, addr: int) -> dict:
        """Extract code object metadata.

        Extracts key attributes from a PyCodeObject including the function
        name, filename, and constants.

        Args:
            addr: Memory address of the code object.

        Returns:
            A dict containing:
                - __type__: Always "code"
                - co_name: Function/lambda name
                - co_filename: Source file path
                - co_consts: Tuple of constants used in the code

        Note:
            Code objects have many internal fields; this extracts only
            the most commonly useful ones for introspection.
        """
        result = {"__type__": "code"}

        try:
            # PyCodeObject has many fields - extract the most useful ones
            # co_consts at +24, co_filename at +112, co_name at +120
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
        self, addr: int, visited: Optional[set] = None, depth: int = 0
    ) -> dict:
        """Extract cell object (closure variable container).

        Cell objects store closure variables captured by nested functions.

        Args:
            addr: Memory address of the cell object.
            visited: Set of visited addresses for cycle detection.
            depth: Current recursion depth.

        Returns:
            A dict containing:
                - __type__: Always "cell"
                - cell_contents: The captured value, or "<empty cell>" if unbound

        Example:
            >>> def outer(x):
            ...     def inner():
            ...         return x
            ...     return inner
            >>> f = outer(42)
            >>> cell = f.__closure__[0]
            >>> pin(cell).xray()
            {'__type__': 'cell', 'cell_contents': 42}
        """
        result = {"__type__": "cell"}

        try:
            # PyCellObject layout:
            # +16: ob_ref (the contained object)
            content_ptr = ctypes.c_void_p.from_address(addr + 16).value
            if content_ptr:
                result["cell_contents"] = self.pull_data_from_address(
                    content_ptr, visited, depth + 1
                )
            else:
                result["cell_contents"] = "<empty cell>"
        except Exception as e:
            result["cell_contents"] = f"<error: {e}>"

        return result

    def _extract_exception(
        self, addr: int, visited: Optional[set] = None, depth: int = 0
    ) -> dict:
        """Extract exception object (BaseException and subclasses).

        Extracts the exception type and args from any exception object.

        Args:
            addr: Memory address of the exception object.
            visited: Set of visited addresses for cycle detection.
            depth: Current recursion depth.

        Returns:
            A dict containing:
                - __type__: Always "exception"
                - exception_type: The exception class name (e.g., "ValueError")
                - args: The exception arguments tuple

        Note:
            All exception types share the same base layout from BaseException,
            so this extractor works for all built-in and custom exceptions.
        """
        result = {"__type__": "exception"}

        try:
            # Get the type name
            _, type_name = self._get_type_info(addr)
            result["exception_type"] = type_name

            # PyBaseExceptionObject layout:
            # +24: args (tuple)
            args_ptr = ctypes.c_void_p.from_address(addr + 24).value
            if args_ptr:
                result["args"] = self.pull_data_from_address(
                    args_ptr, visited, depth + 1
                )
            else:
                result["args"] = ()
        except Exception as e:
            result["exception_type"] = "<unknown>"
            result["args"] = (f"<error extracting: {e}>",)

        return result

    def _extract_property(
        self, addr: int, visited: Optional[set] = None, depth: int = 0
    ) -> dict:
        """Extract property descriptor.

        Extracts the getter, setter, deleter, and docstring from a property.

        Args:
            addr: Memory address of the property object.
            visited: Set of visited addresses for cycle detection.
            depth: Current recursion depth.

        Returns:
            A dict containing:
                - __type__: Always "property"
                - fget: The getter function (if defined)
                - fset: The setter function (if defined)
                - fdel: The deleter function (if defined)
                - __doc__: The property docstring (if defined)

        Example:
            >>> class MyClass:
            ...     @property
            ...     def value(self):
            ...         return self._value
            >>> prop = MyClass.__dict__["value"]
            >>> pin(prop).xray()
            {'__type__': 'property', 'fget': {...}}
        """
        result = {"__type__": "property"}

        try:
            # property object layout:
            # +16: prop_get (fget)
            # +24: prop_set (fset)
            # +32: prop_del (fdel)
            # +40: prop_doc
            fget_ptr = ctypes.c_void_p.from_address(addr + 16).value
            fset_ptr = ctypes.c_void_p.from_address(addr + 24).value
            fdel_ptr = ctypes.c_void_p.from_address(addr + 32).value
            doc_ptr = ctypes.c_void_p.from_address(addr + 40).value

            if fget_ptr:
                result["fget"] = self.pull_data_from_address(
                    fget_ptr, visited, depth + 1
                )
            if fset_ptr:
                result["fset"] = self.pull_data_from_address(
                    fset_ptr, visited, depth + 1
                )
            if fdel_ptr:
                result["fdel"] = self.pull_data_from_address(
                    fdel_ptr, visited, depth + 1
                )
            if doc_ptr:
                result["__doc__"] = self.pull_data_from_address(
                    doc_ptr, visited, depth + 1
                )
        except Exception as e:
            result["error"] = str(e)

        return result

    def _extract_staticmethod(
        self, addr: int, visited: Optional[set] = None, depth: int = 0
    ) -> dict:
        """Extract staticmethod descriptor.

        Extracts the underlying function from a staticmethod wrapper.

        Args:
            addr: Memory address of the staticmethod object.
            visited: Set of visited addresses for cycle detection.
            depth: Current recursion depth.

        Returns:
            A dict containing:
                - __type__: Always "staticmethod"
                - __func__: The wrapped function object
        """
        result = {"__type__": "staticmethod"}

        try:
            # staticmethod layout:
            # +16: sm_callable
            callable_ptr = ctypes.c_void_p.from_address(addr + 16).value
            if callable_ptr:
                result["__func__"] = self.pull_data_from_address(
                    callable_ptr, visited, depth + 1
                )
        except Exception as e:
            result["error"] = str(e)

        return result

    def _extract_classmethod(
        self, addr: int, visited: Optional[set] = None, depth: int = 0
    ) -> dict:
        """Extract classmethod descriptor.

        Extracts the underlying function from a classmethod wrapper.

        Args:
            addr: Memory address of the classmethod object.
            visited: Set of visited addresses for cycle detection.
            depth: Current recursion depth.

        Returns:
            A dict containing:
                - __type__: Always "classmethod"
                - __func__: The wrapped function object
        """
        result = {"__type__": "classmethod"}

        try:
            # classmethod layout:
            # +16: cm_callable
            callable_ptr = ctypes.c_void_p.from_address(addr + 16).value
            if callable_ptr:
                result["__func__"] = self.pull_data_from_address(
                    callable_ptr, visited, depth + 1
                )
        except Exception as e:
            result["error"] = str(e)

        return result

    def _extract_builtin_function(self, addr: int) -> dict:
        """Extract builtin_function_or_method object.

        Extracts the name of a built-in function or bound method.

        Args:
            addr: Memory address of the builtin function object.

        Returns:
            A dict containing:
                - __type__: Always "builtin_function_or_method"
                - __name__: The function name (e.g., "len", "append")

        Example:
            >>> pin(len).xray()
            {'__type__': 'builtin_function_or_method', '__name__': 'len'}
        """
        result = {"__type__": "builtin_function_or_method"}

        try:
            # PyCFunctionObject layout:
            # +16: m_ml (PyMethodDef*)
            ml_ptr = ctypes.c_void_p.from_address(addr + 16).value
            if ml_ptr:
                # PyMethodDef.ml_name is at offset 0
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
        self, addr: int, visited: Optional[set] = None, depth: int = 0
    ) -> dict:
        """Extract generator object metadata.

        Provides basic information about a generator object. Full state
        extraction is limited due to the complex internal structure.

        Args:
            addr: Memory address of the generator object.
            visited: Set of visited addresses for cycle detection.
            depth: Current recursion depth.

        Returns:
            A dict containing:
                - __type__: Always "generator"
                - status: A message indicating limited extraction support

        Note:
            Generator internals vary significantly across Python versions
            and involve frame objects, making full extraction complex.
        """
        result = {"__type__": "generator"}

        # PyGenObject layout is complex and version-dependent
        # For now, return basic info
        result["status"] = "generator object (state not fully extracted)"

        return result

    def _extract_enumerate(
        self, addr: int, visited: Optional[set] = None, depth: int = 0
    ) -> dict:
        """Extract enumerate object.

        Extracts the current index position from an enumerate iterator.

        Args:
            addr: Memory address of the enumerate object.
            visited: Set of visited addresses for cycle detection.
            depth: Current recursion depth.

        Returns:
            A dict containing:
                - __type__: Always "enumerate"
                - start_index: Current index position (advances as iterated)

        Example:
            >>> e = enumerate(['a', 'b', 'c'], start=10)
            >>> pin(e).xray()
            {'__type__': 'enumerate', 'start_index': 10}
        """
        result = {"__type__": "enumerate"}

        try:
            # enumerate layout:
            # +16: en_index (Py_ssize_t)
            # +24: en_sit (iterator)
            # +32: en_result (tuple for reuse)
            index = ctypes.c_ssize_t.from_address(addr + 16).value
            result["start_index"] = index
        except Exception as e:
            result["start_index"] = f"<error: {e}>"

        return result

    def pull_data_from_address(
        self,
        addr: Union[int, ctypes.c_void_p],
        visited: Optional[set] = None,
        depth: int = 0,
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

            # Track containers in visited to avoid cycles
            # Types that recurse and may contain references
            is_container = (
                type_name
                in [
                    "list",
                    "tuple",
                    "dict",
                    "set",
                    "frozenset",
                    "range",
                    "slice",
                    "function",
                    "module",
                    "cell",
                    "property",
                    "staticmethod",
                    "classmethod",
                    "generator",
                    "enumerate",
                ]
                or type_name in self._extractors
                and "Exception" in type_name
            )
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

    def xray(self) -> Any:
        """Extract the logical Python value from the pinned object's memory.

        This method reads the object's memory representation and reconstructs
        the logical Python value. For containers (list, dict, tuple, set),
        this recursively extracts all nested values.

        Returns:
            The reconstructed Python value from memory.

        Example:
            >>> ptr = pin([1, 2, 3])
            >>> ptr.xray()
            [1, 2, 3]
        """
        return self.pull_data_from_address(self.address)

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
        self, keys_ptr: ctypes.POINTER(DictKeysLens)
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
        values_array: Optional[ctypes._Pointer],
        index: int,
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
            ctypes.cast(values_ptr, ctypes.POINTER(ctypes.c_void_p))
            if is_split
            else None
        )

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
                    entry_addr, stride, is_split, values_array, i
                )
                if key_ptr and key_ptr != dummy_ptr:
                    key = self.pull_data_from_address(key_ptr)
                    value = self.pull_data_from_address(val_ptr) if val_ptr else "NULL"
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
                print(f"  ▶ Bucket {i:2d} | Hash: {hex(entry.hash)} | Key: {val}")
            elif key_addr == dummy_ptr:
                print(f"    Bucket {i:2d} | <Dummy>")

    def _examine_tuple(self) -> None:
        """Examine tuple items from memory."""
        size = ctypes.c_ssize_t.from_address(self.address + HEADER_SIZE).value
        # hash_cached(8) starts at +24, items start at +32
        items_array = ctypes.cast(
            self.address + VAR_HEADER_SIZE + 8, ctypes.POINTER(ctypes.c_void_p)
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

    def dump_raw(self, addr: int, length: int = 64, label: str = "MEMORY") -> None:
        """Display hex dump of memory with ASCII representation."""
        print(f"\n--- DEBUG DUMP: {label} AT {hex(addr)} ---")

        try:
            raw_data = ctypes.string_at(addr, length)

            for i in range(0, length, 16):
                offset = f"+{i:03x}"
                chunk = raw_data[i : i + 16]
                hex_vals = " ".join(f"{b:02x}" for b in chunk).ljust(47)
                ascii_vals = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
                print(f"{offset} | {hex_vals} | {ascii_vals}")

        except Exception as e:
            print(f"FAILED TO READ: {e}")
        print("-" * 60)

    def _print_logical_data(self) -> None:
        """Display logical field data from lens."""
        if not self.lens:
            return

        print("\n[ LOGICAL DATA ]")
        for field_info in getattr(self.lens, "_fields_", []):
            field_name = field_info[0]
            val = getattr(self.lens, field_name)
            is_ptr = isinstance(val, int) and field_name.endswith("_ptr")
            display_val = hex(val) if is_ptr else val
            print(f"  FIELD: {field_name.ljust(10)} | VALUE: {display_val}")

    def _print_raw_memory(self, raw_bytes: bytes, total_size: int) -> None:
        """Display raw memory dump in hex format."""
        print("\n[ RAW MEMORY DUMP ]")
        for i in range(0, total_size, 8):
            chunk = raw_bytes[i : i + 8]
            marker = "<- DATA" if i == 16 else ""
            print(f"  +{i:02} | {chunk.hex(' ')} {marker}")

    def examine(self) -> None:
        """Comprehensive examination of Python object memory structure."""
        total_size = sys.getsizeof(self._target)
        # Avoid huge dumps for performance
        dump_size = min(total_size, 256)
        raw_bytes = ctypes.string_at(self.address, dump_size)

        print(f"\n{'=' * 60}")
        print(
            f"X-RAY AT: {hex(self.address)}"
            f" | TYPE: {self.type_name}"
            f" | SIZE: {total_size} bytes"
        )
        print(f"{'=' * 60}")

        print("[ HEADER ]")
        print(f"  +00 | ob_refcnt : {self.header.ob_refcnt}")
        print(f"  +08 | ob_type   : {hex(self.header.ob_type_ptr)}")

        # Type-specific examination
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

        if total_size > 256:
            print("  ... (Memory dump truncated for display)")

        print(f"{'=' * 60}")
