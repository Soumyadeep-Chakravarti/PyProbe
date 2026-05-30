"""Testing the library."""

import os
import sys
from typing import Any

sys.path.insert(0, os.path.abspath("src"))

from pyprobe import pin


def showcase() -> None:
    """Demonstrate the power of the PyProbe Memory Interpreter."""
    print("=" * 60)
    print(
        "PyProbe Memory Interpreter: Industrial Runtime Inspection".center(60)
    )
    print("=" * 60)

    # 1. Primitives & Strings (Multi-encoding)
    print("\n[ STEP 1: Diverse Primitives ]")
    p1: int = 2**100   # Large Int
    p2: float = 3.14159  # Float
    p3: str = "🙂🐍🔥"  # UCS-4 String
    p4: bytes = b"binary\x00data"  # Bytes
    for item in [p1, p2, p3, p4]:
        pin(item).examine()

    # 2. Collections (Graph Inspection)
    print("\n[ STEP 2: Collection Geometries ]")
    # A combined general dictionary
    d: dict[int, str] = {i: str(i) for i in range(5)}
    del d[2]  # Introduce a tombstone
    pin(d).examine()

    # 3. Custom Objects (__dict__ logic)
    print("\n[ STEP 3: Object Internals ]")

    class UserProfile:
        def __init__(self, name: str, age: int) -> None:
            self.name: str = name
            self.age: int = age
            self.preferences: dict[str, Any] = {"theme": "dark", "notifications": True}

    user = UserProfile("Alice", 30)
    pin(user.__dict__).examine()

    # 4. Recursion & Self-Reference
    print("\n[ STEP 4: Cycle Detection ]")
    recursive_list: list[Any] = [1, 2]
    recursive_list.append(recursive_list)
    pin(recursive_list).examine()

    print("\n" + "=" * 60)
    print("Inspection Complete.".center(60))
    print("=" * 60)


if __name__ == "__main__":
    showcase()
