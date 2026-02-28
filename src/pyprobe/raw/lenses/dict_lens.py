import ctypes
'''
layout:

+---------------------+
| dk_refcnt           |
| dk_log2_size        |
| dk_log2_index_bytes |
| dk_kind             |
| dk_version          |
| dk_usable           |
| dk_nentries         |
+---------------------+
| dk_indices[]        |
|                     |
+---------------------+
| dk_entries[]        |
|                     |
+---------------------+
'''

class DictEntry(ctypes.Structure):
    """The individual slot in the hash table"""
    _fields_ = [
        ("me_hash", ctypes.c_ssize_t),
        ("me_key", ctypes.c_void_p),
        ("me_value", ctypes.c_void_p),
    ]

class DictKeysObject(ctypes.Structure):
    _fields_ = [
        ("dk_refcnt", ctypes.c_ssize_t),           # 8 bytes | Offset 0
        
        # These 4 bytes are packed together
        ("dk_log2_size", ctypes.c_uint8),          # 1 byte  | Offset 8
        ("dk_log2_index_bytes", ctypes.c_uint8),    # 1 byte  | Offset 9
        ("dk_kind", ctypes.c_uint8),               # 1 byte  | Offset 10
        ("dk_version_header", ctypes.c_uint8),     # 1 byte  | Offset 11 (Part of version)
        
        # C-Alignment gap usually happens here to align the next 8-byte field
        ("dk_version", ctypes.c_uint32),           # 4 bytes | Offset 12
        
        ("dk_usable", ctypes.c_ssize_t),           # 8 bytes | Offset 16
        ("dk_nentries", ctypes.c_ssize_t),         # 8 bytes | Offset 24
    ]

class DictLens(ctypes.Structure):
    _fields_ = [
        ("ma_used", ctypes.c_ssize_t),
        ("ma_version_tag", ctypes.c_uint64),
        ("ma_keys", ctypes.POINTER(DictKeysObject)),
        ("ma_values", ctypes.c_void_p),
    ]