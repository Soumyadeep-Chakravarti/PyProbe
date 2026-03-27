import sys
import os
import unittest

sys.path.insert(0, os.path.abspath("src"))
from pyprobe import pin

class TestCollections(unittest.TestCase):
    def test_list_tuple(self):
        cases = [
            [1, 2, 3],
            (1, 2, 3),
            [1, (2, 3), [4, 5]],
            [], # Empty list
            (), # Empty tuple
        ]
        for c in cases:
            p = pin(c)
            val = p.pull_data_from_address(p.address)
            self.assertEqual(val, c, f"Failed for collection: {repr(c)}")

    def test_dict_simple(self):
        cases = [
            {"a": 1, "b": 2},
            {1: "a", 2.5: "b", (1,2): "c"},
            {}, # Empty dict
        ]
        for c in cases:
            p = pin(c)
            val = p.pull_data_from_address(p.address)
            self.assertEqual(val, c, f"Failed for dict: {repr(c)}")

    def test_dict_deletions(self):
        d = {i: str(i) for i in range(10)}
        del d[2]
        del d[5]
        del d[8]
        p = pin(d)
        val = p.pull_data_from_address(p.address)
        self.assertEqual(val, d, "Failed for dict with deletions (tombstones).")

    def test_sets(self):
        cases = [
            {1, 2, 3},
            {"a", "b", "c"},
            frozenset([1, 2, 3]),
            set(),
        ]
        for c in cases:
            p = pin(c)
            val = p.pull_data_from_address(p.address)
            self.assertEqual(val, c, f"Failed for set/frozenset: {repr(c)}")

if __name__ == "__main__":
    unittest.main()
