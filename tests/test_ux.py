import sys
import os
import unittest
import json
import types

sys.path.insert(0, os.path.abspath("src"))

from pyprobe import (
    explain, audit, audit_str, to_dict, to_json, compare, compare_str,
    PyProbeSafetyError, PyProbeSecurityError,
)
from pyprobe.core.ux import (
    _Color, SafetyVerdict, MutationTarget, AuditReport,
    _estimate_size, _mutation_function_name, _get_constraints,
)


class TestColorSupport(unittest.TestCase):
    def test_color_disabled_by_default(self):
        """Colors disabled when stdout is not a TTY (pytest captures)."""
        # In test runner, stdout is not a TTY
        result = _Color.enabled()
        self.assertFalse(result)

    def test_color_force_enable(self):
        os.environ["PYPROBE_COLOR"] = "always"
        try:
            self.assertTrue(_Color.enabled())
        finally:
            del os.environ["PYPROBE_COLOR"]

    def test_color_force_disable(self):
        os.environ["PYPROBE_COLOR"] = "never"
        try:
            self.assertFalse(_Color.enabled())
        finally:
            del os.environ["PYPROBE_COLOR"]

    def test_color_c_wraps_text(self):
        os.environ["PYPROBE_COLOR"] = "always"
        try:
            result = _Color.c("hello", _Color.RED)
            self.assertIn("hello", result)
            self.assertIn("\033[91m", result)
            self.assertIn("\033[0m", result)
        finally:
            del os.environ["PYPROBE_COLOR"]

    def test_color_c_no_wrap_when_disabled(self):
        os.environ["PYPROBE_COLOR"] = "never"
        try:
            result = _Color.c("hello", _Color.RED)
            self.assertEqual(result, "hello")
        finally:
            del os.environ["PYPROBE_COLOR"]

    def test_colorblind_mode(self):
        os.environ["PYPROBE_COLOR_MODE"] = "colorblind"
        try:
            self.assertTrue(_Color.colorblind())
        finally:
            del os.environ["PYPROBE_COLOR_MODE"]

    def test_colorblind_default_normal(self):
        if "PYPROBE_COLOR_MODE" in os.environ:
            del os.environ["PYPROBE_COLOR_MODE"]
        self.assertFalse(_Color.colorblind())


class TestSafetyVerdict(unittest.TestCase):
    def test_safe_value(self):
        self.assertEqual(SafetyVerdict.SAFE.value, "safe")

    def test_unsafe_value(self):
        self.assertEqual(SafetyVerdict.UNSAFE.value, "unsafe")


class TestMutationTarget(unittest.TestCase):
    def test_creation(self):
        t = MutationTarget(
            object_type="int",
            object_repr="42",
            memory_address=0x12345678,
            size_bytes=28,
            verdict=SafetyVerdict.SAFE,
            reason="Sole reference",
            mutation_function="mutate_int",
            constraints=["Must fit in 1 digit"],
        )
        self.assertEqual(t.object_type, "int")
        self.assertEqual(t.verdict, SafetyVerdict.SAFE)
        self.assertEqual(t.constraints, ["Must fit in 1 digit"])

    def test_defaults(self):
        t = MutationTarget(
            object_type="float",
            object_repr="3.14",
            memory_address=0x1234,
            size_bytes=24,
            verdict=SafetyVerdict.UNSAFE,
            reason="Shared",
            mutation_function="mutate_float",
        )
        self.assertEqual(t.constraints, [])


class TestAuditReport(unittest.TestCase):
    def test_counts(self):
        targets = [
            MutationTarget("int", "1", 0x1, 28, SafetyVerdict.SAFE, "ok", "mutate_int"),
            MutationTarget("int", "2", 0x2, 28, SafetyVerdict.UNSAFE, "no", "mutate_int"),
        ]
        report = AuditReport(targets=targets, total_safe=1, total_unsafe=1)
        self.assertEqual(report.total_safe, 1)
        self.assertEqual(report.total_unsafe, 1)
        self.assertEqual(len(report.targets), 2)


class TestEstimateSize(unittest.TestCase):
    def test_int(self):
        self.assertGreater(_estimate_size(42), 0)

    def test_float(self):
        self.assertGreater(_estimate_size(3.14), 0)

    def test_str(self):
        self.assertGreater(_estimate_size("hello"), 0)

    def test_list(self):
        self.assertGreater(_estimate_size([1, 2, 3]), 0)

    def test_dict(self):
        self.assertGreater(_estimate_size({"a": 1}), 0)

    def test_bytes(self):
        self.assertGreater(_estimate_size(b"hello"), 0)

    def test_bool(self):
        self.assertGreater(_estimate_size(True), 0)

    def test_unsupported_type(self):
        self.assertGreater(_estimate_size(object()), 0)


class TestMutationFunctionName(unittest.TestCase):
    def test_float(self):
        self.assertEqual(_mutation_function_name(3.14), "mutate_float")

    def test_int(self):
        self.assertEqual(_mutation_function_name(42), "mutate_int")

    def test_list(self):
        self.assertEqual(_mutation_function_name([1]), "safe_list_swap")

    def test_dict(self):
        self.assertEqual(_mutation_function_name({"a": 1}), "safe_dict_value_swap")

    def test_bytes(self):
        self.assertEqual(_mutation_function_name(b"hi"), "mutate_bytes")

    def test_str(self):
        self.assertEqual(_mutation_function_name("hi"), "mutate_str")

    def test_unsupported(self):
        self.assertEqual(_mutation_function_name(object()), "unsupported")

    def test_set(self):
        self.assertEqual(_mutation_function_name({1, 2}), "unsupported")

    def test_tuple(self):
        self.assertEqual(_mutation_function_name((1, 2)), "unsupported")


class TestGetConstraints(unittest.TestCase):
    def test_int_constraints(self):
        c = _get_constraints(1000)
        self.assertTrue(any("digit" in s for s in c))

    def test_cached_int_constraint(self):
        c = _get_constraints(42)
        self.assertTrue(any("Cached" in s for s in c))

    def test_float_constraints(self):
        c = _get_constraints(3.14)
        self.assertTrue(any("finite" in s for s in c))

    def test_str_constraints(self):
        c = _get_constraints("hello")
        self.assertTrue(any("5 bytes" in s for s in c))

    def test_list_constraints(self):
        c = _get_constraints([1, 2, 3])
        self.assertTrue(any("Index" in s for s in c))

    def test_dict_constraints(self):
        c = _get_constraints({"x": 1})
        self.assertTrue(any("Key" in s for s in c))

    def test_bytes_constraints(self):
        c = _get_constraints(b"hello")
        self.assertTrue(any("5 bytes" in s for s in c))


class TestExplain(unittest.TestCase):
    def test_explain_float(self):
        result = explain(3.14)
        self.assertIn("float", result)
        self.assertIn("mutate_float", result)
        self.assertIn("finite float", result)
        self.assertIn("Address:", result)
        self.assertIn("Size:", result)
        self.assertIn("Verdict:", result)

    def test_explain_int(self):
        result = explain(1000)
        self.assertIn("int", result)
        self.assertIn("mutate_int", result)

    def test_explain_list(self):
        result = explain([1, 2, 3])
        self.assertIn("list", result)
        self.assertIn("safe_list_swap", result)

    def test_explain_dict(self):
        result = explain({"a": 1})
        self.assertIn("dict", result)
        self.assertIn("safe_dict_value_swap", result)

    def test_explain_unsupported_type(self):
        result = explain(set([1, 2]))
        self.assertIn("unsupported", result)
        self.assertIn("No direct mutation", result)

    def test_explain_contains_example(self):
        result = explain(3.14)
        self.assertIn("Example:", result)
        self.assertIn("mutate_float", result)

    def test_explain_list_example(self):
        result = explain([1, 2])
        self.assertIn("safe_list_swap(my_list", result)


class TestToDict(unittest.TestCase):
    def test_float_keys(self):
        d = to_dict(3.14)
        self.assertEqual(d["type"], "float")
        self.assertIn("repr", d)
        self.assertIn("address", d)
        self.assertIn("size_bytes", d)
        self.assertIn("safe_to_mutate", d)
        self.assertIn("reason", d)
        self.assertEqual(d["mutation_function"], "mutate_float")
        self.assertIn("constraints", d)

    def test_int_keys(self):
        d = to_dict(1000)
        self.assertEqual(d["type"], "int")
        self.assertEqual(d["mutation_function"], "mutate_int")

    def test_str_keys(self):
        d = to_dict("hello")
        self.assertEqual(d["type"], "str")
        self.assertEqual(d["mutation_function"], "mutate_str")

    def test_address_is_hex_string(self):
        d = to_dict(42)
        self.assertTrue(d["address"].startswith("0x"))

    def test_constraints_is_list(self):
        d = to_dict(1000)
        self.assertIsInstance(d["constraints"], list)


class TestToJson(unittest.TestCase):
    def test_valid_json(self):
        s = to_json(3.14)
        d = json.loads(s)
        self.assertEqual(d["type"], "float")

    def test_indent(self):
        s = to_json(3.14, indent=4)
        self.assertIn("    ", s)  # Should have indentation

    def test_no_indent(self):
        s = to_json(3.14, indent=0)
        # Should be compact JSON
        self.assertNotIn("\n  ", s)


class TestCompare(unittest.TestCase):
    def test_same_type(self):
        r = compare(1000, 2000)
        self.assertTrue(r["type_match"])
        self.assertEqual(r["type_a"], "int")
        self.assertEqual(r["type_b"], "int")

    def test_different_type(self):
        r = compare(1000, "hello")
        self.assertFalse(r["type_match"])
        self.assertIn("Cannot swap", r["note"])

    def test_same_type_same_size(self):
        r = compare([1, 2], [3, 4])
        self.assertTrue(r["type_match"])
        self.assertTrue(r["size_match"])

    def test_same_type_different_size(self):
        r = compare([1, 2], [3, 4, 5])
        self.assertTrue(r["type_match"])
        self.assertFalse(r["size_match"])

    def test_compatible_when_safe(self):
        r = compare(1000, 2000)
        self.assertIn("compatible", r)

    def test_all_keys_present(self):
        r = compare(1000, 2000)
        for key in ["type_a", "type_b", "type_match", "safe_a", "safe_b",
                     "reason_a", "reason_b", "function_a", "function_b",
                     "compatible"]:
            self.assertIn(key, r)

    def test_dict_same_keys(self):
        r = compare({"a": 1}, {"b": 2})
        self.assertTrue(r["type_match"])
        self.assertTrue(r["size_match"])


class TestCompareStr(unittest.TestCase):
    def test_output_contains_info(self):
        s = compare_str(1000, 2000)
        self.assertIn("Compare", s)
        self.assertIn("int", s)
        self.assertIn("Type match", s)
        self.assertIn("Compatible", s)

    def test_different_types(self):
        s = compare_str(1000, "hello")
        self.assertIn("No", s)


class TestAudit(unittest.TestCase):
    def test_explicit_scope(self):
        report = audit({"x": 42, "y": "hello", "z": [1, 2]})
        self.assertIsInstance(report, AuditReport)
        self.assertGreater(len(report.targets), 0)

    def test_all_targets_have_expected_fields(self):
        report = audit({"x": 1000, "y": 3.14})
        for t in report.targets:
            self.assertIsInstance(t.object_type, str)
            self.assertIsInstance(t.object_repr, str)
            self.assertIsInstance(t.memory_address, int)
            self.assertIsInstance(t.size_bytes, int)
            self.assertIsInstance(t.verdict, SafetyVerdict)
            self.assertIsInstance(t.reason, str)
            self.assertIsInstance(t.mutation_function, str)
            self.assertIsInstance(t.constraints, list)

    def test_safe_count(self):
        report = audit({"x": 1000})
        self.assertEqual(report.total_safe + report.total_unsafe, len(report.targets))

    def test_unsupported_type_excluded(self):
        report = audit({"s": set([1]), "t": (1, 2), "x": 42})
        types_found = {t.object_type for t in report.targets}
        self.assertNotIn("set", types_found)
        self.assertNotIn("tuple", types_found)
        self.assertIn("int", types_found)

    def test_underscore_keys_excluded(self):
        report = audit({"_private": 42, "public": 100})
        names = {t.object_repr for t in report.targets}
        # _private should not appear
        self.assertTrue(all("_private" not in t.object_repr for t in report.targets))

    def test_empty_scope(self):
        report = audit({})
        self.assertEqual(len(report.targets), 0)
        self.assertEqual(report.total_safe, 0)
        self.assertEqual(report.total_unsafe, 0)


class TestAuditStr(unittest.TestCase):
    def test_output_string(self):
        s = audit_str({"x": 42})
        self.assertIsInstance(s, str)
        self.assertIn("PyProbe Audit Report", s)
        self.assertIn("Safe:", s)
        self.assertIn("Unsafe:", s)

    def test_empty_scope_message(self):
        s = audit_str({})
        self.assertIn("No mutation targets found", s)


class TestExplainUnsupported(unittest.TestCase):
    def test_custom_class(self):
        class MyClass:
            pass
        result = explain(MyClass())
        self.assertIn("unsupported", result)

    def test_module(self):
        result = explain(json)
        # modules are unsupported
        self.assertIn("unsupported", result)


class TestAuditDefaultScope(unittest.TestCase):
    def test_audit_none_uses_caller_locals(self):
        x = 42
        y = "hello"
        report = audit()
        self.assertIsInstance(report, AuditReport)
        # Should find at least some targets from this local scope
        self.assertGreater(len(report.targets), 0)


if __name__ == "__main__":
    unittest.main()
