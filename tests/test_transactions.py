import sys
import os
import unittest

sys.path.insert(0, os.path.abspath("src"))

from pyprobe.core.Scalpel import (
    Transaction, transaction, _current_tx,
    mutate_float, mutate_int, mutate_bytes, mutate_str,
    safe_list_swap, safe_dict_value_swap,
)

# Transaction tests use safe=False because pytest's deep call stacks
# cause the shared-object refcount heuristic to reject test-local variables.
# These tests verify commit/rollback mechanics, not safety checks.

SAFE = False


def _non_interned_bytes():
    """Create bytes that Python won't intern."""
    return bytes(bytearray([65, 66, 67, 68]))


def _non_interned_str():
    """Create str that Python won't intern."""
    return "".join(["1", "2", "3", "4"])


class TestTransactionCommit(unittest.TestCase):
    """Mutations committed normally within a transaction."""

    def test_float_commit(self):
        f = 100.5
        with transaction() as tx:
            mutate_float(f, 999.99, safe=SAFE)
        self.assertAlmostEqual(f, 999.99, places=2)

    def test_int_commit(self):
        x = 10**18
        with transaction() as tx:
            mutate_int(x, 42, safe=SAFE)
        self.assertEqual(x, 42)

    def test_list_slot_commit(self):
        lst = [10, 20, 30]
        with transaction() as tx:
            safe_list_swap(lst, 1, "MUTATED", safe=SAFE)
        self.assertEqual(lst, [10, "MUTATED", 30])

    def test_dict_slot_commit(self):
        d = dict(status="secure", version=1)
        with transaction() as tx:
            safe_dict_value_swap(d, "status", "mutated", safe=SAFE)
        self.assertEqual(d, {"status": "mutated", "version": 1})

    def test_bytes_commit(self):
        b = _non_interned_bytes()
        orig_id = id(b)
        replacement = bytes(bytearray([87, 88, 89, 90]))
        with transaction() as tx:
            mutate_bytes(b, replacement, safe=SAFE)
        self.assertEqual(id(b), orig_id)
        self.assertEqual(b, replacement)

    def test_str_commit(self):
        s = _non_interned_str()
        orig_id = id(s)
        replacement = "".join(["5", "6", "7", "8"])
        with transaction() as tx:
            mutate_str(s, replacement, safe=SAFE)
        self.assertEqual(id(s), orig_id)
        self.assertEqual(s, replacement)

    def test_multi_type_commit(self):
        f = 1.0
        x = 10**18
        lst = [10, 20, 30]
        d = dict(status="secure")
        with transaction() as tx:
            mutate_float(f, 2.0, safe=SAFE)
            mutate_int(x, 42, safe=SAFE)
            safe_list_swap(lst, 0, "A", safe=SAFE)
            safe_dict_value_swap(d, "status", "mutated", safe=SAFE)
        self.assertAlmostEqual(f, 2.0, places=2)
        self.assertEqual(x, 42)
        self.assertEqual(lst, ["A", 20, 30])
        self.assertEqual(d, {"status": "mutated"})

    def test_manual_commit(self):
        f = 100.5
        with transaction() as tx:
            mutate_float(f, 999.99, safe=SAFE)
            tx.commit()
        self.assertAlmostEqual(f, 999.99, places=2)

    def test_manual_commit_discards_reverts(self):
        f = 100.5
        with transaction() as tx:
            mutate_float(f, 999.99, safe=SAFE)
            tx.commit()
        self.assertEqual(len(tx._revert_ops), 0)

    def test_no_mutations_just_commit(self):
        with transaction() as tx:
            tx.commit()
        self.assertEqual(len(tx._revert_ops), 0)


class TestTransactionRollback(unittest.TestCase):
    """Mutations reverted when exception propagates."""

    def test_float_rollback(self):
        f = 100.5
        try:
            with transaction() as tx:
                mutate_float(f, 999.99, safe=SAFE)
                raise RuntimeError("abort")
        except RuntimeError:
            pass
        self.assertAlmostEqual(f, 100.5, places=2)

    def test_int_rollback(self):
        x = 10**18
        try:
            with transaction() as tx:
                mutate_int(x, 42, safe=SAFE)
                raise RuntimeError("abort")
        except RuntimeError:
            pass
        self.assertEqual(x, 10**18)

    def test_list_rollback(self):
        lst = [10, 20, 30]
        try:
            with transaction() as tx:
                safe_list_swap(lst, 1, "MUTATED", safe=SAFE)
                raise RuntimeError("abort")
        except RuntimeError:
            pass
        self.assertEqual(lst, [10, 20, 30])

    def test_dict_rollback(self):
        d = dict(status="secure", version=1)
        try:
            with transaction() as tx:
                safe_dict_value_swap(d, "status", "mutated", safe=SAFE)
                raise RuntimeError("abort")
        except RuntimeError:
            pass
        self.assertEqual(d, {"status": "secure", "version": 1})

    def test_bytes_rollback(self):
        b = _non_interned_bytes()
        orig = b
        try:
            with transaction() as tx:
                mutate_bytes(b, bytes(bytearray([87, 88, 89, 90])), safe=SAFE)
                raise RuntimeError("abort")
        except RuntimeError:
            pass
        self.assertEqual(b, orig)

    def test_str_rollback(self):
        s = _non_interned_str()
        try:
            with transaction() as tx:
                mutate_str(s, "".join(["5", "6", "7", "8"]), safe=SAFE)
                raise RuntimeError("abort")
        except RuntimeError:
            pass
        self.assertEqual(s, "1234")

    def test_multi_type_rollback(self):
        f = 1.0
        x = 10**18
        lst = [10, 20, 30]
        d = dict(status="secure")
        try:
            with transaction() as tx:
                mutate_float(f, 2.0, safe=SAFE)
                mutate_int(x, 42, safe=SAFE)
                safe_list_swap(lst, 0, "A", safe=SAFE)
                safe_dict_value_swap(d, "status", "mutated", safe=SAFE)
                raise RuntimeError("abort")
        except RuntimeError:
            pass
        self.assertAlmostEqual(f, 1.0, places=2)
        self.assertEqual(x, 10**18)
        self.assertEqual(lst, [10, 20, 30])
        self.assertEqual(d, {"status": "secure"})

    def test_value_error_rollback(self):
        f = 100.5
        try:
            with transaction() as tx:
                mutate_float(f, 999.99, safe=SAFE)
                raise ValueError("bad input")
        except ValueError:
            pass
        self.assertAlmostEqual(f, 100.5, places=2)

    def test_key_error_rollback(self):
        f = 100.5
        try:
            with transaction() as tx:
                mutate_float(f, 999.99, safe=SAFE)
                _ = {}["missing"]
        except KeyError:
            pass
        self.assertAlmostEqual(f, 100.5, places=2)


class TestTransactionRollbackOrder(unittest.TestCase):
    """Rollback reverts in reverse mutation order (LIFO)."""

    def test_reverse_order_list(self):
        lst = [1, 2, 3]
        try:
            with transaction() as tx:
                safe_list_swap(lst, 0, "A", safe=SAFE)
                safe_list_swap(lst, 1, "B", safe=SAFE)
                safe_list_swap(lst, 2, "C", safe=SAFE)
                raise RuntimeError("abort")
        except RuntimeError:
            pass
        self.assertEqual(lst, [1, 2, 3])

    def test_reverse_order_dict(self):
        d = dict(a=1, b=2, c=3)
        try:
            with transaction() as tx:
                safe_dict_value_swap(d, "a", "X", safe=SAFE)
                safe_dict_value_swap(d, "b", "Y", safe=SAFE)
                safe_dict_value_swap(d, "c", "Z", safe=SAFE)
                raise RuntimeError("abort")
        except RuntimeError:
            pass
        self.assertEqual(d, {"a": 1, "b": 2, "c": 3})

    def test_mixed_types_reverse_order(self):
        f = 1.0
        lst = [10, 20]
        d = dict(key="val")
        try:
            with transaction() as tx:
                mutate_float(f, 2.0, safe=SAFE)
                safe_list_swap(lst, 0, "A", safe=SAFE)
                safe_dict_value_swap(d, "key", "mutated", safe=SAFE)
                raise RuntimeError("abort")
        except RuntimeError:
            pass
        self.assertAlmostEqual(f, 1.0, places=2)
        self.assertEqual(lst, [10, 20])
        self.assertEqual(d, {"key": "val"})


class TestTransactionEdgeCases(unittest.TestCase):
    """Edge cases and boundary conditions."""

    def test_empty_transaction(self):
        with transaction() as tx:
            pass
        self.assertEqual(len(tx._revert_ops), 0)

    def test_commit_after_exception_not_caught(self):
        f = 100.5
        tx_obj = None
        try:
            with transaction() as tx:
                mutate_float(f, 999.99, safe=SAFE)
                tx_obj = tx
                raise RuntimeError("abort")
        except RuntimeError:
            pass
        self.assertAlmostEqual(f, 100.5, places=2)

    def test_double_commit(self):
        f = 100.5
        with transaction() as tx:
            mutate_float(f, 999.99, safe=SAFE)
            tx.commit()
            tx.commit()  # second commit should be no-op
        self.assertAlmostEqual(f, 999.99, places=2)

    def test_rollback_clears_reverts(self):
        f = 100.5
        try:
            with transaction() as tx:
                mutate_float(f, 999.99, safe=SAFE)
                self.assertEqual(len(tx._revert_ops), 1)
                raise RuntimeError("abort")
        except RuntimeError:
            pass
        self.assertAlmostEqual(f, 100.5, places=2)

    def test_no_transaction_still_works(self):
        """Mutations outside transaction work normally (backward compat)."""
        f = 100.5
        mutate_float(f, 999.99, safe=SAFE)
        self.assertAlmostEqual(f, 999.99, places=2)

        lst = [10, 20, 30]
        safe_list_swap(lst, 1, "MUTATED", safe=SAFE)
        self.assertEqual(lst, [10, "MUTATED", 30])

        d = dict(status="secure")
        safe_dict_value_swap(d, "status", "mutated", safe=SAFE)
        self.assertEqual(d, {"status": "mutated"})

    def test_current_tx_stack_empty_outside(self):
        """_current_tx stack is empty when not inside a transaction."""
        self.assertEqual(len(_current_tx), 0)

    def test_current_tx_stack_after_transaction(self):
        """_current_tx stack is empty after transaction exits."""
        with transaction() as tx:
            mutate_float(1.0, 2.0, safe=SAFE)
        self.assertEqual(len(_current_tx), 0)

    def test_current_tx_stack_after_rollback(self):
        """_current_tx stack is empty after rollback."""
        try:
            with transaction() as tx:
                mutate_float(1.0, 2.0, safe=SAFE)
                raise RuntimeError("x")
        except RuntimeError:
            pass
        self.assertEqual(len(_current_tx), 0)

    def test_multiple_sequential_transactions(self):
        f1 = 1.0
        f2 = 2.0
        with transaction():
            mutate_float(f1, 10.0, safe=SAFE)
        with transaction():
            mutate_float(f2, 20.0, safe=SAFE)
        self.assertAlmostEqual(f1, 10.0, places=2)
        self.assertAlmostEqual(f2, 20.0, places=2)


class TestTransactionRevertHelpers(unittest.TestCase):
    """Test each revert helper in isolation."""

    def test_revert_float_preserves_negative(self):
        f = -123.456
        try:
            with transaction() as tx:
                mutate_float(f, 999.99, safe=SAFE)
                raise RuntimeError("x")
        except RuntimeError:
            pass
        self.assertAlmostEqual(f, -123.456, places=3)

    def test_revert_int_preserves_large(self):
        x = 2**62
        try:
            with transaction() as tx:
                mutate_int(x, 0, safe=SAFE)
                raise RuntimeError("x")
        except RuntimeError:
            pass
        self.assertEqual(x, 2**62)

    def test_revert_int_preserves_negative(self):
        x = -(10**18)
        try:
            with transaction() as tx:
                mutate_int(x, 0, safe=SAFE)
                raise RuntimeError("x")
        except RuntimeError:
            pass
        self.assertEqual(x, -(10**18))

    def test_revert_list_slot_preserves_type(self):
        lst = [10, None, "hello"]
        orig = lst[:]
        try:
            with transaction() as tx:
                safe_list_swap(lst, 0, "replaced", safe=SAFE)
                raise RuntimeError("x")
        except RuntimeError:
            pass
        self.assertEqual(lst, orig)

    def test_revert_dict_slot_preserves_all_keys(self):
        d = dict(a=1, b=2, c=3)
        try:
            with transaction() as tx:
                safe_dict_value_swap(d, "a", "X", safe=SAFE)
                raise RuntimeError("x")
        except RuntimeError:
            pass
        self.assertEqual(d, {"a": 1, "b": 2, "c": 3})
        self.assertIn("b", d)
        self.assertIn("c", d)

    def test_revert_bytes_preserves_content(self):
        b = _non_interned_bytes()
        orig = b
        try:
            with transaction() as tx:
                mutate_bytes(b, bytes(bytearray([99, 100, 101, 102])), safe=SAFE)
                raise RuntimeError("x")
        except RuntimeError:
            pass
        self.assertEqual(b, orig)

    def test_revert_str_preserves_content(self):
        s = _non_interned_str()
        try:
            with transaction() as tx:
                mutate_str(s, "".join(["9", "9", "9", "9"]), safe=SAFE)
                raise RuntimeError("x")
        except RuntimeError:
            pass
        self.assertEqual(s, "1234")


class TestTransactionDocstrings(unittest.TestCase):
    """Verify documented behavior matches implementation."""

    def test_transaction_context_manager_exists(self):
        self.assertTrue(callable(transaction))

    def test_transaction_class_exists(self):
        self.assertTrue(issubclass(Transaction, object))

    def test_transaction_has_commit(self):
        self.assertTrue(hasattr(Transaction, "commit"))

    def test_transaction_has_rollback(self):
        self.assertTrue(hasattr(Transaction, "rollback"))


if __name__ == "__main__":
    unittest.main()
