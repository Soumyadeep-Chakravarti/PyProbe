import ctypes

class DictLens(ctypes.Structure):
    """Surgical view of PyDictObject fields (starts after PyObject_HEAD)."""
    _fields_ = [
        ("ma_used", ctypes.c_ssize_t),
        ("ma_version_tag", ctypes.c_uint64),
        ("ma_keys", ctypes.c_void_p), # Cast manually in engine
        ("ma_values", ctypes.c_void_p),
    ]

class DictKeysLens(ctypes.Structure):
    """Surgical view of PyDictKeysObject fields (full struct as it's not a PyObject)."""
    _fields_ = [
        ("dk_refcnt", ctypes.c_ssize_t),
        ("dk_log2_size", ctypes.c_uint8),
        ("dk_log2_index_bytes", ctypes.c_uint8),
        ("dk_kind", ctypes.c_uint8),
        ("dk_version_header", ctypes.c_uint8),
        ("dk_version", ctypes.c_uint32),
        ("dk_usable", ctypes.c_ssize_t),
        ("dk_nentries", ctypes.c_ssize_t),
    ]
