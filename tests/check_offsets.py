import sys
import os
import ctypes
sys.path.insert(0, os.path.abspath("src"))
from pyprobe.raw.lenses.dict_lens import DictKeysLens

def check_lens():
    print(f"Size of DictKeysLens: {ctypes.sizeof(DictKeysLens)}")
    for field in DictKeysLens._fields_:
        name = field[0]
        offset = getattr(DictKeysLens, name).offset
        print(f"Field: {name.ljust(20)} | Offset: {offset}")

if __name__ == "__main__":
    check_lens()
