from .core.pointer.engine import Pointer

def pin(obj):
    return Pointer(target=obj)

def pin_addr(addr):
    return Pointer(address=addr)