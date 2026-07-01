"""Comprehensive safety tests for pyprobe.core.safety module.

Tests cover:
- Address validation (bounds, alignment)
- Detection functions (immortal, cached, interned, type, module, code, function)
- Snapshot and verify lifecycle
- Comprehensive safety check
- Shared object detection
"""

import sys
import os
import types
import unittest
import ctypes

sys.path.insert(0, os.path.abspath("src"))
from pyprobe.core.safety import (
    validate_address,
    validate_read_access,
    validate_write_access,
    is_immortal,
    is_cached_int,
    is_interned_string,
    is_interned_bytes,
    is_type_object,
    is_module,
    is_code_object,
    is_function,
    snapshot,
    verify,
    comprehensive_safety_check,
    IMMORTAL_REFCOUNT_THRESHOLD,
    MIN_SAFE_ADDRESS,
    MAX_SAFE_ADDRESS,
    SMALL_INT_MIN,
    SMALL_INT_MAX,
)
from pyprobe.core.common import (
    PyProbeIntegrityError,
    PyProbeSafetyError,
    PyProbeSecurityError,
)


class TestValidateAddress(unittest.TestCase):
    """Tests for validate_address()."""

    def test_null_pointer_raises(self):
        with self.assertRaises(PyProbeIntegrityError) as ctx:
            validate_address(0)
        self.assertIn("Null pointer", str(ctx.exception))

    def test_too_low_raises(self):
        with self.assertRaises(PyProbeIntegrityError) as ctx:
            validate_address(0x100)
        self.assertIn("too low", str(ctx.exception))

    def test_too_high_raises(self):
        with self.assertRaises(PyProbeIntegrityError) as ctx:
            validate_address(0x800000000000)
        self.assertIn("too high", str(ctx.exception))

    def test_unaligned_raises(self):
        with self.assertRaises(PyProbeIntegrityError) as ctx:
            validate_address(MIN_SAFE_ADDRESS + 3)
        self.assertIn("Unaligned", str(ctx.exception))

    def test_valid_address_passes(self):
        # Should not raise
        validate_address(MIN_SAFE_ADDRESS)


class TestValidateReadAccess(unittest.TestCase):
    """Tests for validate_read_access()."""

    def test_valid_readable_address(self):
        buf = (ctypes.c_byte * 8)(0)
        addr = ctypes.addressof(buf)
        # Should not raise
        validate_read_access(addr)

    def test_invalid_address_raises(self):
        with self.assertRaises(PyProbeIntegrityError):
            validate_read_access(0)


class TestValidateWriteAccess(unittest.TestCase):
    """Tests for validate_write_access()."""

    def test_valid_writable_address(self):
        buf = (ctypes.c_byte * 8)(0)
        addr = ctypes.addressof(buf)
        # Should not raise
        validate_write_access(addr)

    def test_invalid_address_raises(self):
        with self.assertRaises(PyProbeIntegrityError):
            validate_write_access(0)


class TestIsImmortal(unittest.TestCase):
    """Tests for is_immortal()."""

    def test_none_is_immortal(self):
        self.assertTrue(is_immortal(None))

    def test_true_is_immortal(self):
        self.assertTrue(is_immortal(True))

    def test_false_is_immortal(self):
        self.assertTrue(is_immortal(False))

    def test_ellipsis_is_immortal(self):
        self.assertTrue(is_immortal(...))

    def test_small_int_is_immortal(self):
        self.assertTrue(is_immortal(0))
        self.assertTrue(is_immortal(1))
        self.assertTrue(is_immortal(256))

    def test_large_int_not_immortal(self):
        # Very large ints are not cached/immortal
        self.assertFalse(is_immortal(999999))


class TestIsCachedInt(unittest.TestCase):
    """Tests for is_cached_int()."""

    def test_cached_int_min(self):
        self.assertTrue(is_cached_int(SMALL_INT_MIN))

    def test_cached_int_max(self):
        self.assertTrue(is_cached_int(SMALL_INT_MAX))

    def test_cached_int_zero(self):
        self.assertTrue(is_cached_int(0))

    def test_cached_int_negative(self):
        self.assertTrue(is_cached_int(-5))

    def test_non_cached_int(self):
        self.assertFalse(is_cached_int(SMALL_INT_MAX + 1))
        self.assertFalse(is_cached_int(SMALL_INT_MIN - 1))

    def test_non_int_returns_false(self):
        self.assertFalse(is_cached_int("not an int"))
        self.assertFalse(is_cached_int(3.14))


class TestIsInternedString(unittest.TestCase):
    """Tests for is_interned_string()."""

    def test_single_char_is_interned(self):
        self.assertTrue(is_interned_string("a"))
        self.assertTrue(is_interned_string(""))

    def test_identifier_is_interned(self):
        self.assertTrue(is_interned_string("hello"))
        self.assertTrue(is_interned_string("_private"))
        self.assertTrue(is_interned_string("camelCase"))

    def test_non_identifier_not_interned(self):
        # Strings with spaces are not identifiers
        self.assertFalse(is_interned_string("hello world"))

    def test_non_string_returns_false(self):
        self.assertFalse(is_interned_string(123))


class TestIsInternedBytes(unittest.TestCase):
    """Tests for is_interned_bytes()."""

    def test_empty_bytes_interned(self):
        self.assertTrue(is_interned_bytes(b""))

    def test_single_byte_interned(self):
        self.assertTrue(is_interned_bytes(b"a"))

    def test_multi_byte_not_interned(self):
        self.assertFalse(is_interned_bytes(b"hello"))

    def test_non_bytes_returns_false(self):
        self.assertFalse(is_interned_bytes("not bytes"))


class TestIsTypeObject(unittest.TestCase):
    """Tests for is_type_object()."""

    def test_builtin_type(self):
        self.assertTrue(is_type_object(int))
        self.assertTrue(is_type_object(str))
        self.assertTrue(is_type_object(list))

    def test_custom_class(self):
        class MyClass:
            pass
        self.assertTrue(is_type_object(MyClass))

    def test_instance_not_type(self):
        self.assertFalse(is_type_object(42))
        self.assertFalse(is_type_object("hello"))


class TestIsModule(unittest.TestCase):
    """Tests for is_module()."""

    def test_os_module(self):
        self.assertTrue(is_module(os))

    def test_types_module(self):
        self.assertTrue(is_module(types))

    def test_non_module(self):
        self.assertFalse(is_module("not a module"))


class TestIsCodeObject(unittest.TestCase):
    """Tests for is_code_object()."""

    def test_code_object(self):
        def foo():
            return 1
        self.assertTrue(is_code_object(foo.__code__))

    def test_lambda_code(self):
        f = lambda: None
        self.assertTrue(is_code_object(f.__code__))

    def test_non_code(self):
        self.assertFalse(is_code_object(42))


class TestIsFunction(unittest.TestCase):
    """Tests for is_function()."""

    def test_regular_function(self):
        def foo():
            pass
        self.assertTrue(is_function(foo))

    def test_lambda(self):
        f = lambda: None
        self.assertTrue(is_function(f))

    def test_method(self):
        class MyClass:
            def method(self):
                pass
        obj = MyClass()
        self.assertTrue(is_function(obj.method))

    def test_non_function(self):
        self.assertFalse(is_function(42))
        self.assertFalse(is_function(int))


class TestSnapshot(unittest.TestCase):
    """Tests for snapshot()."""

    def test_snapshot_int(self):
        obj = 42
        snap = snapshot(obj)
        self.assertEqual(snap.type_name, "int")
        self.assertEqual(snap.address, id(obj))
        self.assertGreater(snap.refcount, 0)

    def test_snapshot_float(self):
        obj = 3.14
        snap = snapshot(obj)
        self.assertEqual(snap.type_name, "float")
        self.assertEqual(snap.float_value, 3.14)

    def test_snapshot_string(self):
        obj = "hello"
        snap = snapshot(obj)
        self.assertEqual(snap.type_name, "str")
        self.assertIsNotNone(snap.raw_bytes)

    def test_snapshot_bytes(self):
        obj = b"hello"
        snap = snapshot(obj)
        self.assertEqual(snap.type_name, "bytes")
        self.assertIsNotNone(snap.raw_bytes)

    def test_snapshot_list(self):
        obj = [1, 2, 3]
        snap = snapshot(obj)
        self.assertEqual(snap.type_name, "list")
        self.assertEqual(snap.ob_size, 3)

    def test_snapshot_tuple(self):
        obj = (1, 2, 3)
        snap = snapshot(obj)
        self.assertEqual(snap.type_name, "tuple")


class TestVerify(unittest.TestCase):
    """Tests for verify()."""

    def test_verify_same_object(self):
        obj = [1, 2, 3]
        snap = snapshot(obj)
        # No mutation - should pass
        verify(obj, snap, strict=True)

    def test_verify_address_changed(self):
        obj = [1, 2, 3]
        snap = snapshot(obj)
        # Create a different object with different address
        other = [4, 5, 6]
        with self.assertRaises(PyProbeIntegrityError) as ctx:
            verify(other, snap, strict=True)
        self.assertIn("moved", str(ctx.exception))

    def test_verify_refcount_changed(self):
        obj = [1, 2, 3]
        snap = snapshot(obj)
        # Increase refcount artificially
        refs = [obj, obj, obj, obj, obj, obj, obj, obj, obj, obj]
        with self.assertRaises(PyProbeSafetyError) as ctx:
            verify(obj, snap, strict=True)
        self.assertIn("Refcount changed", str(ctx.exception))
        del refs

    def test_verify_non_strict_warns(self):
        obj = [1, 2, 3]
        snap = snapshot(obj)
        other = [4, 5, 6]
        # Should not raise in non-strict mode
        verify(other, snap, strict=False)


class TestComprehensiveSafetyCheck(unittest.TestCase):
    """Tests for comprehensive_safety_check()."""

    def test_type_object_raises_security(self):
        with self.assertRaises(PyProbeSecurityError):
            comprehensive_safety_check(int)

    def test_module_raises_security(self):
        with self.assertRaises(PyProbeSecurityError):
            comprehensive_safety_check(os)

    def test_code_object_raises_security(self):
        def foo():
            pass
        with self.assertRaises(PyProbeSecurityError):
            comprehensive_safety_check(foo.__code__)

    def test_function_raises_security(self):
        def foo():
            pass
        with self.assertRaises(PyProbeSecurityError):
            comprehensive_safety_check(foo)

    def test_immortal_raises_security(self):
        with self.assertRaises(PyProbeSecurityError):
            comprehensive_safety_check(None)

    def test_interned_string_raises_security(self):
        with self.assertRaises(PyProbeSecurityError):
            comprehensive_safety_check("hello")  # identifier, interned

    def test_cached_int_raises_safety(self):
        # Use check_immortal=False to reach the cached int check
        # (cached ints are also immortal, so immortal check fires first)
        with self.assertRaises(PyProbeSafetyError):
            comprehensive_safety_check(42, check_immortal=False)

    def test_normal_object_passes(self):
        # Non-cached int should pass
        comprehensive_safety_check(999999)

    def test_custom_object_passes(self):
        class MyClass:
            pass
        obj = MyClass()
        comprehensive_safety_check(obj)


class TestSharedObjectDetection(unittest.TestCase):
    """Tests for shared object detection in assert_safe()."""

    def test_shared_object_raises(self):
        from pyprobe.core.Scalpel import assert_safe
        obj = [1, 2, 3]
        # Create many references
        refs = [obj for _ in range(20)]
        with self.assertRaises(PyProbeSafetyError) as ctx:
            assert_safe(obj)
        self.assertIn("Shared object", str(ctx.exception))
        del refs

    def test_single_ref_passes(self):
        from pyprobe.core.Scalpel import assert_safe
        obj = [1, 2, 3]
        # Should not raise (only 1 reference + stack)
        assert_safe(obj)


if __name__ == "__main__":
    unittest.main()
