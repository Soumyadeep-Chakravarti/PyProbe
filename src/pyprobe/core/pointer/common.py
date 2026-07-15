"""Shared types and constants for the pointer module."""

import builtins
from typing import Dict, Set

VisitedSet = Set[int]

# PyObject_HEAD
HEADER_SIZE = 16

# PyVarObject_HEAD
VAR_HEADER_SIZE = 24

# Pre-computed set of all builtin exception type names
EXCEPTION_NAMES: set[str] = set()
for _name in dir(builtins):
    _obj = getattr(builtins, _name, None)
    if isinstance(_obj, type) and issubclass(_obj, BaseException):
        EXCEPTION_NAMES.add(_name)

# Cached type name lookups
TYPE_NAME_CACHE: Dict[int, str] = {}

# Sentinel for unset target parameter
UNSET = object()
