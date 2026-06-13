from typing import Any, Dict, Optional

from .core import Pointer
from .core.common import (
    PyProbeError,
    PyProbeFatalError,
    PyProbeIntegrityError,
    PyProbeSafetyError,
    PyProbeSecurityError,
    PyProbeWarning,
)
from .core.log import get_ring
from .core.ux import explain, audit, audit_str, to_dict, to_json, compare, compare_str


def pin(obj: Any, safe: bool = True) -> Pointer:
    """Create a Pointer pinning a live Python object.

    Args:
        obj: Python object to pin.
        safe: When True (default), run safety checks before mutations.
              Set to False to bypass PyProbeSafetyError checks.
    """
    return Pointer(target=obj, safe=safe)


def pin_addr(addr: int, safe: bool = True) -> Pointer:
    """Create a Pointer to a raw memory address.

    Args:
        addr: Memory address to point to.
        safe: When True (default), run safety checks before mutations.
              Set to False to bypass PyProbeSafetyError checks.
    """
    return Pointer(address=addr, safe=safe)