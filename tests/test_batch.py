import sys
import os
import unittest

sys.path.insert(0, os.path.abspath("src"))

from pyprobe.core.Scalpel import (
    mutate_batch, transaction, _current_tx,
    mutate_float, mutate_int, mutate_bytes, mutate_str,
    safe_list_swap, safe_dict_value_swap,
    PyProbeSafetyError, PyProbeIntegrityError, PyProbeSecurityError,
)

SAFE = False


def _non_interned_bytes():
    return bytes(bytearray([65, 66, 67, 68]))


def _non_interned_str():
    return "".join(["1", "2", "3", "4"])


class TestBatchCommit(unittest.TestCase):
    """All mutations in a batch commit successfully."""

    def test_batch_float_int(self):
        f = 100.5
        x = 10**18
        mutate_batch([
            (mutate_float, f, 999.99),
            (mutate_int, x, 42),
        ], safe=SAFE)
        self.assertAlmostEqual(f, 999.99, places=2)
        self.assertEqual(x, 42)

    def test_batch_all_types(self):
        f = 100.5
        x = 10**18
        lst = [10, 20, 30]
        d = {"a": 1, "b": 2}
        b = _non_interned_bytes()
        s = _non_interned_str()
        mutate_batch([
            (mutate_float, f, 3.14),
            (mutate_int, x, 99),
            (safe_list_swap, lst, 0, "X"),
            (safe_dict_value_swap, d, "a", 999),
            (mutate_bytes, b, b"WXYZ"),
            (mutate_str, s, "5678"),
        ], safe=SAFE)
        self.assertAlmostEqual(f, 3.14, places=2)
        self.assertEqual(x, 99)
        self.assertEqual(lst, ["X", 20, 30])
        self.assertEqual(d, {"a": 999, "b": 2})
        self.assertEqual(b, b"WXYZ")
        self.assertEqual(s, "5678")


class TestBatchRollback(unittest.TestCase):
    """On failure, all prior mutations are rolled back."""

    def test_rollback_on_integrity_error(self):
        f = 100.5
        x = 10**18
        with self.assertRaises(PyProbeIntegrityError):
            mutate_batch([
                (mutate_float, f, 3.14),
                (mutate_str, _non_interned_str(), "too_long"),  # length mismatch
            ], safe=SAFE)
        self.assertAlmostEqual(f, 100.5, places=2)

    def test_rollback_mid_batch(self):
        f = 100.5
        x = 10**18
        lst = [10, 20, 30]
        with self.assertRaises(MemoryError):
            mutate_batch([
                (mutate_float, f, 3.14),
                (mutate_int, x, 1),   # OK - 1 digit
                (mutate_int, x, 10**30),  # Overflow
                (safe_list_swap, lst, 0, 999),  # never reached
            ], safe=SAFE)
        self.assertAlmostEqual(f, 100.5, places=2)
        self.assertEqual(x, 10**18)
        self.assertEqual(lst, [10, 20, 30])

    def test_rollback_on_security_error(self):
        b = _non_interned_bytes()
        with self.assertRaises(PyProbeSecurityError):
            mutate_batch([
                (mutate_bytes, b, b"WXYZ"),
                (mutate_int, 42, 99),  # cached int - hard block
            ], safe=True)
        self.assertEqual(b, b"ABCD")


class TestBatchSafety(unittest.TestCase):
    """safe=True catches shared refs / unsafe targets."""

    def test_safe_mode_rejects_shared(self):
        f = 100.5
        f2 = f
        with self.assertRaises(PyProbeSafetyError):
            mutate_batch([
                (mutate_float, f, 3.14),
            ], safe=True)


class TestBatchEdgeCases(unittest.TestCase):
    """Empty batch, single op, etc."""

    def test_empty_batch(self):
        mutate_batch([], safe=SAFE)

    def test_single_operation(self):
        f = 100.5
        mutate_batch([
            (mutate_float, f, 3.14),
        ], safe=SAFE)
        self.assertAlmostEqual(f, 3.14, places=2)

    def test_transaction_stack_cleaned_after_error(self):
        self.assertEqual(len(_current_tx), 0)
        with self.assertRaises(PyProbeIntegrityError):
            mutate_batch([
                (mutate_bytes, _non_interned_bytes(), b"too_long"),
            ], safe=SAFE)
        self.assertEqual(len(_current_tx), 0)


class TestBatchIntegration(unittest.TestCase):
    """Batch works with existing transaction context manager."""

    def test_nested_in_transaction(self):
        f = 100.5
        x = 10**18
        with transaction():
            mutate_batch([
                (mutate_float, f, 3.14),
                (mutate_int, x, 42),
            ], safe=SAFE)
        self.assertAlmostEqual(f, 3.14, places=2)
        self.assertEqual(x, 42)


if __name__ == "__main__":
    unittest.main()
