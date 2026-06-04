"""Testing the library."""

import os
import sys
from typing import Any, Dict, Union

sys.path.insert(0, os.path.abspath("src"))

from pyprobe import pin


def showcase() -> None:
    """Demonstrate PyProbe's live memory introspection and mutation."""
    print("PyProbe — Memory Inspector")
    print("=" * 50)

    # 1. Primitives & Strings (Multi-encoding)
    print("\n[ STEP 1: Diverse Primitives ]")
    p1: int = 2**100   # Large Int
    p2: float = 3.14159  # Float
    p3: str = "🙂🐍🔥"  # UCS-4 String
    p4: bytes = b"binary\x00data"  # Bytes
    primitives: list[Union[int, float, str, bytes]] = [p1, p2, p3, p4]
    for item in primitives:
        pin(item).examine()

    # 2. Collections (Graph Inspection)
    print("\n[ STEP 2: Collection Geometries ]")
    # A combined general dictionary
    d: dict[int, str] = {i: str(i) for i in range(5)}
    del d[2]  # Introduce a tombstone
    print(d)
    pin(d).examine()

    # 3. Custom Objects (__dict__ logic)
    print("\n[ STEP 3: Object Internals ]")

    class UserProfile:
        def __init__(self, name: str, age: int) -> None:
            self.name: str = name
            self.age: int = age
            self.preferences: Dict[str, Union[str, bool]] = {"theme": "dark", "notifications": True}

    user = UserProfile("Alice", 30)
    pin(user.__dict__).examine()

    # 4. Recursion & Self-Reference
    print("\n[ STEP 4: Cycle Detection ]")
    recursive_list: list[Any] = [1, 2]
    recursive_list.append(recursive_list)
    print(recursive_list)
    pin(recursive_list).examine()

    print("\n" + "=" * 60)
    print("Inspection Complete.".center(60))
    print("=" * 60)


if __name__ == "__main__":
    showcase()
