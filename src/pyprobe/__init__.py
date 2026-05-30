from typing import Any

from .core.pointer.engine import Pointer


def pin(obj: Any) -> Pointer:
    """Create a Pointer to inspect an object."""
    return Pointer(target=obj)


def pin_addr(addr: int) -> Pointer:
    """Create a Pointer from a memory address."""
    return Pointer(address=addr)