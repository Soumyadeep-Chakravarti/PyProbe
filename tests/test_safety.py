import sys
import os
import unittest
import ctypes
import random

sys.path.insert(0, os.path.abspath("src"))
from pyprobe import pin

class TestSafety(unittest.TestCase):
    def test_null_pointer(self):
        p = pin(None)
        # Should handle NULL (0x0) gracefully via _normalize_address
        res = p.pull_data_from_address(0)
        self.assertEqual(res, "NULL")

    def test_corrupt_type(self):
        # Create a buffer that looks like an object but has a garbage type pointer
        buf = (ctypes.c_byte * 32)(0)
        addr = ctypes.addressof(buf)
        # Set a garbage type pointer at +8
        ctypes.c_void_p.from_address(addr + 8).value = 0xdeadbeef
        
        p = pin(1) # Just to get an engine instance
        res = p.pull_data_from_address(addr)
        self.assertIn("<Corrupt Type", str(res))

    def test_unmapped_memory(self):
        # Try to read from a very low address (usually unmapped)
        p = pin(1)
        res = p.pull_data_from_address(0x100)
        # Our safety guard in _get_type_info should catch < 0x1000 addresses
        self.assertIn("<Bad Address", str(res))

if __name__ == "__main__":
    unittest.main()
