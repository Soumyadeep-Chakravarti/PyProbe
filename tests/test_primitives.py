import sys
import os
import unittest

sys.path.insert(0, os.path.abspath("src"))
from pyprobe import pin

class TestPrimitives(unittest.TestCase):
    def test_ints(self):
        cases = [0, 1, -1, 2**64, -2**64, 2**120, -2**120]
        for c in cases:
            p = pin(c)
            val = p.pull_data_from_address(p.address)
            self.assertEqual(val, c, f"Failed for int: {c}")

    def test_floats(self):
        cases = [0.0, 1.1, -1.1, 3.14159, 1e20, -1e20]
        for c in cases:
            p = pin(c)
            val = p.pull_data_from_address(p.address)
            self.assertEqual(val, c, f"Failed for float: {c}")

    def test_unicode_strings(self):
        cases = [
            "ascii",
            "latin1: é à",
            "ucs2: 你好",
            "ucs4: 🙂🐍🔥",
            "" # Empty string
        ]
        for c in cases:
            p = pin(c)
            val = p.pull_data_from_address(p.address)
            self.assertEqual(val, c, f"Failed for string: {repr(c)}")

    def test_bytes(self):
        cases = [b"", b"hello", b"binary\x00data\xff", b"\x00" * 10]
        for c in cases:
            p = pin(c)
            val = p.pull_data_from_address(p.address)
            self.assertEqual(val, c, f"Failed for bytes: {repr(c)}")

if __name__ == "__main__":
    unittest.main()
