"""Dictheaders."""

import ctypes


class DictKeysObject(ctypes.Structure):
    """DictKeysObject."""

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


class PyDictObject(ctypes.Structure):
    """DictObject."""

    _fields_ = [
        ("ob_refcnt", ctypes.c_ssize_t),
        ("ob_type_ptr", ctypes.c_void_p),
        ("ma_used", ctypes.c_ssize_t),
        ("ma_version_tag", ctypes.c_uint64),
        ("ma_keys", ctypes.POINTER(DictKeysObject)),
        ("ma_values", ctypes.c_void_p),
    ]
