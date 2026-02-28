import ctypes
import sys
from pyprobe.raw.headers.py_object import PyObjectHeader
from pyprobe.raw.headers.py_type import PyTypeObject
from pyprobe.raw.lenses.float_lens import FloatLens
from pyprobe.raw.lenses.int_lens import IntLens
from pyprobe.raw.lenses.list_lens import ListLens
from pyprobe.raw.lenses.str_lens import StringLens
from pyprobe.raw.lenses.dict_lens import DictLens, DictEntry, DictKeysObject # Note the double import

HEADER_SIZE = 16 

class Pointer:
    def __init__(self, target):
        self._target = target
        self.address = id(target)
        self.header = PyObjectHeader.from_address(self.address)

        type_struct = PyTypeObject.from_address(self.header.ob_type_ptr)
        self.type_name = type_struct.tp_name.decode('utf-8')

        self.data_addr = self.address + HEADER_SIZE
        self.lens = self._get_lens()

    def _get_lens(self):
        lenses = {
            'int': IntLens,
            'float': FloatLens,
            'list': ListLens,
            'str': StringLens,
            'dict': DictLens # Now registered
        }
        lens_cls = lenses.get(self.type_name)
        return lens_cls.from_address(self.data_addr) if lens_cls else None

    def pull_data_from_address(self, addr):
        """ The 'Surgical Grabber' """

        if hasattr(addr, 'value'):
            addr = addr.value
        if addr is None:
            return "NULL"

        h = PyObjectHeader.from_address(addr)
        t_struct = PyTypeObject.from_address(h.ob_type_ptr)
        t_name = t_struct.tp_name.decode('utf-8')

        if t_name == 'int':
            return ctypes.c_uint32.from_address(addr + 24).value
        elif t_name == 'float':
            return ctypes.c_double.from_address(addr + 16).value
        elif t_name == 'str':
            s_len = ctypes.c_ssize_t.from_address(addr + 16).value
            return ctypes.string_at(addr + 40, s_len).decode('utf-8')
        return f"<{t_name} @ {hex(addr)}>"

    

    def _examine_dict(self):
        keys_ptr = self.lens.ma_keys
        if not keys_ptr:
            return

        keys_obj = keys_ptr.contents
        base_addr = ctypes.cast(keys_ptr, ctypes.c_void_p).value
        
        # SHIFT: Move back 8 bytes from our previous guess
        # Header(24) + Indices(8) = 32. 
        # This aligns perfectly with the end of dk_indices.
        entries_addr = base_addr + 32
        ENTRY_STRIDE = 28

        print(f"\n[ KEY-OBJECT ALLOCATION AT {hex(base_addr)} ]")
        print(f"  Entries Start (Aligned): {hex(entries_addr)}")

        print(f"\n[ PARSED DENSE ENTRIES ]")
        
        for i in range(keys_obj.dk_nentries):
            this_entry_addr = entries_addr + (i * ENTRY_STRIDE)
            
            try:
                # Now these offsets will line up with the C-struct
                hash_val = ctypes.c_ssize_t.from_address(this_entry_addr).value     # +0
                key_ptr  = ctypes.c_void_p.from_address(this_entry_addr + 8).value   # +8
                val_ptr  = ctypes.c_void_p.from_address(this_entry_addr + 16).value  # +16
                
                if key_ptr:
                    k = self.pull_data_from_address(key_ptr)
                    v = self.pull_data_from_address(val_ptr)
                    print(f"  ▶ Slot {i} | Hash: {hash_val:x} | Key: {k} | Val: {v}")
                else:
                    print(f"    Slot {i} | <Empty/Dummy Slot>")
            except Exception as e:
                print(f"    Slot {i} | Memory Error: {e}")
    
    def examine(self):
        total_size = sys.getsizeof(self._target)
        raw_bytes = ctypes.string_at(self.address, total_size)

        print(f"\n{'='*60}")
        print(f"X-RAY AT: {hex(self.address)} | TYPE: {self.type_name} | SIZE: {total_size} bytes")
        print(f"{'='*60}")

        print(f"[ HEADER ]")
        print(f"  +00 | ob_refcnt : {self.header.ob_refcnt}")
        print(f"  +08 | ob_type   : {hex(self.header.ob_type_ptr)}")

        # --- DYNAMIC DISPATCH ---
        if self.type_name == 'list':
            print(f"\n[ LIST CONTENTS (Follow Pointers) ]")
            item_array = self.lens.ob_item
            for i in range(self.lens.ob_size):
                obj_addr = item_array[i]
                actual_value = self.pull_data_from_address(obj_addr)
                
                temp_h = PyObjectHeader.from_address(obj_addr)
                temp_t = PyTypeObject.from_address(temp_h.ob_type_ptr)
                t_name = temp_t.tp_name.decode('utf-8')
                print(f"  Item {i} | Addr: {hex(obj_addr)} | {t_name.ljust(5)}: {actual_value}")

        elif self.type_name == 'dict':
            self._examine_dict()

        # Logical Data
        if self.lens:
            print(f"\n[ LOGICAL DATA ]")
            for field_name, _ in self.lens._fields_:
                val = getattr(self.lens, field_name)
                display_val = hex(ctypes.addressof(val.contents)) if hasattr(val, 'contents') else val
                print(f"  FIELD: {field_name.ljust(10)} | VALUE: {display_val}")

        # Raw Hex Dump
        print(f"\n[ RAW MEMORY DUMP ]")
        for i in range(0, total_size, 8):
            chunk = raw_bytes[i:i+8]
            marker = "<- DATA" if i == 16 else ""
            print(f"  +{i:02} | {chunk.hex(' ')} {marker}")
        print(f"{'='*60}")
    
    def dump_raw(self, addr, length=64, label="MEMORY"):
        """ A surgical hex dump tool with ASCII side-car """
        print(f"\n--- DEBUG DUMP: {label} AT {hex(addr)} ---")
        
        try:
            # Grab the block of memory
            raw_data = ctypes.string_at(addr, length)
            
            for i in range(0, length, 16):
                # 1. Offset
                offset = f"+{i:03x}"
                
                # 2. Hex Bytes
                chunk = raw_data[i:i+16]
                hex_vals = ' '.join(f"{b:02x}" for b in chunk)
                # Pad hex section if chunk is < 16 bytes
                hex_vals = hex_vals.ljust(47)
                
                # 3. ASCII side-car
                ascii_vals = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
                
                print(f"{offset} | {hex_vals} | {ascii_vals}")
                
        except Exception as e:
            print(f"FAILED TO READ: {e}")
        print("-" * 60)