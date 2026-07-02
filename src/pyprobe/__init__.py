from typing import Any

from .core import Pointer


def pin(obj: Any) -> Pointer:
    """Create a Pointer pinning a live Python object."""
    return Pointer(target=obj)


def pin_addr(addr: int) -> Pointer:
    """Create a Pointer to a raw memory address."""
    return Pointer(address=addr)