from typing import Any, Dict, Optional

from .core import Pointer
from .core.common import (
    PyProbeError,
    PyProbeIntegrityError,
    PyProbeSafetyError,
    PyProbeSecurityError,
    PyProbeWarning,
)
from .core.ux import explain, audit, audit_str, to_dict, to_json, compare, compare_str


def pin(obj: Any) -> Pointer:
    """Create a Pointer pinning a live Python object."""
    return Pointer(target=obj)


def pin_addr(addr: int) -> Pointer:
    """Create a Pointer to a raw memory address."""
    return Pointer(address=addr)