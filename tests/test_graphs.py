import sys
import os
import unittest
from typing import cast

sys.path.insert(0, os.path.abspath("src"))
from pyprobe import pin

class TestGraphs(unittest.TestCase):
    def test_cycles(self) -> None:
        # 1. Cyclic List
        a: list[object] = [1, 2]
        a.append(a)
        p1 = pin(a)
        val1 = p1.pull_data_from_address(p1.address)
        self.assertEqual(val1[2], f"<Cycle @ {hex(p1.address)}>")

        # 2. Cyclic Dict
        b: dict[str, object] = {"key": "value"}
        b["self"] = b
        p2 = pin(b)
        val2 = p2.pull_data_from_address(p2.address)
        self.assertEqual(val2["self"], f"<Cycle @ {hex(p2.address)}>")

        # 3. Intertwined Cycle
        c: list[object] = [10]
        d: dict[str, object] = {"link": c}
        c.append(d)
        p3 = pin(c)
        val3 = p3.pull_data_from_address(p3.address)
        self.assertEqual(val3[1]["link"], f"<Cycle @ {hex(p3.address)}>")

    def test_depth_limit(self) -> None:
        # Test cutoff with a small limit for verification
        # Deep structure exceeding industrial depth limit (100)
        curr: dict[str, object] = {}
        root: dict[str, object] = curr
        for _ in range(120):
            curr["n"] = {}
            curr = curr["n"]
        
        p = pin(root)
        val = p.pull_data_from_address(p.address)
        
        # We don't need to be exact on the index due to key/val recursion 
        # just verify that as we go deeper, we eventually hit a string cutoff
        current: object = val
        found_cutoff = False
        for _ in range(110):
            if isinstance(current, str) and current.startswith("<Max Depth"):
                found_cutoff = True
                break
            current_dict: dict[str, object] = cast(dict[str, object], current)
            if "n" not in current_dict:
                # Key might have been hit by depth limit
                for k in current_dict.keys():
                    if k.startswith("<Max Depth"):
                        found_cutoff = True
                break
            current = current_dict["n"]
            
        self.assertTrue(found_cutoff, "Should have encountered a depth limit cutoff")

if __name__ == "__main__":
    _ = unittest.main()
