"""Tests for extended type support in PyProbe xray."""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath("src"))
from pyprobe import pin


class TestBoolAndNone(unittest.TestCase):
    """Tests for bool and NoneType extraction."""

    def test_bool_true(self):
        p = pin(True)
        val = p.xray()
        self.assertIs(val, True)

    def test_bool_false(self):
        p = pin(False)
        val = p.xray()
        self.assertIs(val, False)

    def test_none(self):
        p = pin(None)
        val = p.xray()
        self.assertIsNone(val)


class TestNumericTypes(unittest.TestCase):
    """Tests for complex number extraction."""

    def test_complex_positive(self):
        c = 3.0 + 4.0j
        p = pin(c)
        val = p.xray()
        self.assertEqual(val, c)

    def test_complex_negative(self):
        c = -1.5 - 2.5j
        p = pin(c)
        val = p.xray()
        self.assertEqual(val, c)

    def test_complex_zero(self):
        c = 0j
        p = pin(c)
        val = p.xray()
        self.assertEqual(val, c)

    def test_complex_real_only(self):
        c = complex(5.0, 0.0)
        p = pin(c)
        val = p.xray()
        self.assertEqual(val, c)

    def test_complex_imag_only(self):
        c = complex(0.0, 7.0)
        p = pin(c)
        val = p.xray()
        self.assertEqual(val, c)


class TestSequenceTypes(unittest.TestCase):
    """Tests for range, slice, bytearray, and memoryview extraction."""

    def test_range_simple(self):
        r = range(10)
        p = pin(r)
        val = p.xray()
        self.assertEqual(val, r)

    def test_range_with_step(self):
        r = range(1, 20, 3)
        p = pin(r)
        val = p.xray()
        self.assertEqual(val, r)

    def test_range_negative(self):
        r = range(10, 0, -1)
        p = pin(r)
        val = p.xray()
        self.assertEqual(val, r)

    def test_slice_simple(self):
        s = slice(1, 10)
        p = pin(s)
        val = p.xray()
        self.assertEqual(val.start, s.start)
        self.assertEqual(val.stop, s.stop)
        self.assertEqual(val.step, s.step)

    def test_slice_with_step(self):
        s = slice(0, 100, 5)
        p = pin(s)
        val = p.xray()
        self.assertEqual(val.start, s.start)
        self.assertEqual(val.stop, s.stop)
        self.assertEqual(val.step, s.step)

    def test_slice_with_none(self):
        s = slice(None, 10, None)
        p = pin(s)
        val = p.xray()
        self.assertEqual(val.start, s.start)
        self.assertEqual(val.stop, s.stop)
        self.assertEqual(val.step, s.step)

    def test_bytearray_simple(self):
        ba = bytearray(b"hello world")
        p = pin(ba)
        val = p.xray()
        self.assertEqual(val, ba)

    def test_bytearray_empty(self):
        ba = bytearray()
        p = pin(ba)
        val = p.xray()
        self.assertEqual(val, ba)

    def test_bytearray_binary(self):
        ba = bytearray(b"\x00\x01\x02\xff\xfe")
        p = pin(ba)
        val = p.xray()
        self.assertEqual(val, ba)

    def test_memoryview(self):
        """memoryview xray returns bytes, not the memoryview itself."""
        data = b"hello"
        mv = memoryview(data)
        p = pin(mv)
        val = p.xray()
        self.assertEqual(val, data)


class TestFunctionExtraction(unittest.TestCase):
    """Tests for function object extraction."""

    def test_function_simple(self):
        def my_func():
            pass

        p = pin(my_func)
        val = p.xray()
        self.assertEqual(val["__type__"], "function")
        self.assertEqual(val["__name__"], "my_func")

    def test_function_with_defaults(self):
        def func_with_defaults(x, y=10, z="hello"):
            return x + y

        p = pin(func_with_defaults)
        val = p.xray()
        self.assertEqual(val["__name__"], "func_with_defaults")
        self.assertEqual(val["__defaults__"], (10, "hello"))

    def test_function_with_doc(self):
        def documented_func():
            """This is the docstring."""
            pass

        p = pin(documented_func)
        val = p.xray()
        self.assertEqual(val["__doc__"], "This is the docstring.")

    def test_lambda(self):
        f = lambda x: x * 2
        p = pin(f)
        val = p.xray()
        self.assertEqual(val["__type__"], "function")
        self.assertEqual(val["__name__"], "<lambda>")


class TestTypeExtraction(unittest.TestCase):
    """Tests for type object extraction."""

    def test_builtin_type_int(self):
        p = pin(int)
        val = p.xray()
        self.assertEqual(val["__type__"], "type")
        self.assertEqual(val["__name__"], "int")

    def test_builtin_type_str(self):
        p = pin(str)
        val = p.xray()
        self.assertEqual(val["__type__"], "type")
        self.assertEqual(val["__name__"], "str")

    def test_builtin_type_list(self):
        p = pin(list)
        val = p.xray()
        self.assertEqual(val["__type__"], "type")
        self.assertEqual(val["__name__"], "list")

    def test_custom_class(self):
        class MyCustomClass:
            pass

        p = pin(MyCustomClass)
        val = p.xray()
        self.assertEqual(val["__type__"], "type")
        self.assertEqual(val["__name__"], "MyCustomClass")

    def test_type_of_type(self):
        p = pin(type)
        val = p.xray()
        self.assertEqual(val["__type__"], "type")
        self.assertEqual(val["__name__"], "type")


class TestModuleExtraction(unittest.TestCase):
    """Tests for module object extraction."""

    def test_sys_module(self):
        p = pin(sys)
        val = p.xray()
        self.assertEqual(val["__type__"], "module")
        self.assertEqual(val["__name__"], "sys")
        self.assertIn("__dict_keys__", val)

    def test_os_module(self):
        p = pin(os)
        val = p.xray()
        self.assertEqual(val["__type__"], "module")
        self.assertEqual(val["__name__"], "os")

    def test_module_has_dict_keys(self):
        p = pin(sys)
        val = p.xray()
        self.assertIsInstance(val["__dict_keys__"], list)
        # Check for common attributes that are in the first 20 keys
        self.assertIn("__name__", val["__dict_keys__"])


class TestCodeExtraction(unittest.TestCase):
    """Tests for code object extraction."""

    def test_function_code_object(self):
        def sample_func(x, y):
            return x + y

        code = sample_func.__code__
        p = pin(code)
        val = p.xray()
        self.assertEqual(val["__type__"], "code")
        self.assertEqual(val["co_name"], "sample_func")

    def test_code_with_constants(self):
        def func_with_consts():
            x = 42
            return "hello"

        code = func_with_consts.__code__
        p = pin(code)
        val = p.xray()
        self.assertEqual(val["__type__"], "code")
        self.assertIn("co_consts", val)
        # Constants should include None (return value), 42, and "hello"
        self.assertIn(42, val["co_consts"])
        self.assertIn("hello", val["co_consts"])

    def test_lambda_code_object(self):
        f = lambda x: x * 2
        code = f.__code__
        p = pin(code)
        val = p.xray()
        self.assertEqual(val["__type__"], "code")
        self.assertEqual(val["co_name"], "<lambda>")


class TestCellExtraction(unittest.TestCase):
    """Tests for cell object (closure) extraction."""

    def test_closure_cell(self):
        def outer(x):
            def inner():
                return x

            return inner

        inner_func = outer(42)
        # Get the cell object from the closure
        cell = inner_func.__closure__[0]
        p = pin(cell)
        val = p.xray()
        self.assertEqual(val["__type__"], "cell")
        self.assertEqual(val["cell_contents"], 42)

    def test_closure_cell_string(self):
        def outer(msg):
            def inner():
                return msg

            return inner

        inner_func = outer("hello world")
        cell = inner_func.__closure__[0]
        p = pin(cell)
        val = p.xray()
        self.assertEqual(val["__type__"], "cell")
        self.assertEqual(val["cell_contents"], "hello world")

    def test_closure_multiple_cells(self):
        def outer(a, b):
            def inner():
                return a + b

            return inner

        inner_func = outer(10, 20)
        # First cell
        cell_a = inner_func.__closure__[0]
        p_a = pin(cell_a)
        val_a = p_a.xray()
        self.assertEqual(val_a["__type__"], "cell")

        # Second cell
        cell_b = inner_func.__closure__[1]
        p_b = pin(cell_b)
        val_b = p_b.xray()
        self.assertEqual(val_b["__type__"], "cell")

        # Combined should have both values (order may vary)
        contents = {val_a["cell_contents"], val_b["cell_contents"]}
        self.assertEqual(contents, {10, 20})


class TestExceptionExtraction(unittest.TestCase):
    """Tests for exception object extraction."""

    def test_value_error(self):
        exc = ValueError("invalid value")
        p = pin(exc)
        val = p.xray()
        self.assertEqual(val["__type__"], "exception")
        self.assertEqual(val["exception_type"], "ValueError")
        self.assertEqual(val["args"], ("invalid value",))

    def test_type_error(self):
        exc = TypeError("wrong type")
        p = pin(exc)
        val = p.xray()
        self.assertEqual(val["__type__"], "exception")
        self.assertEqual(val["exception_type"], "TypeError")
        self.assertEqual(val["args"], ("wrong type",))

    def test_key_error(self):
        exc = KeyError("missing_key")
        p = pin(exc)
        val = p.xray()
        self.assertEqual(val["__type__"], "exception")
        self.assertEqual(val["exception_type"], "KeyError")
        self.assertEqual(val["args"], ("missing_key",))

    def test_exception_multiple_args(self):
        # Note: OSError(2, ...) creates FileNotFoundError in Python
        exc = FileNotFoundError(2, "No such file", "test.txt")
        p = pin(exc)
        val = p.xray()
        self.assertEqual(val["__type__"], "exception")
        self.assertEqual(val["exception_type"], "FileNotFoundError")
        self.assertIn(2, val["args"])
        self.assertIn("No such file", val["args"])

    def test_runtime_error(self):
        exc = RuntimeError("something went wrong")
        p = pin(exc)
        val = p.xray()
        self.assertEqual(val["__type__"], "exception")
        self.assertEqual(val["exception_type"], "RuntimeError")

    def test_stop_iteration(self):
        exc = StopIteration("done")
        p = pin(exc)
        val = p.xray()
        self.assertEqual(val["__type__"], "exception")
        self.assertEqual(val["exception_type"], "StopIteration")


class TestDescriptorExtraction(unittest.TestCase):
    """Tests for property, staticmethod, and classmethod extraction."""

    def test_property_fget_only(self):
        class MyClass:
            @property
            def value(self):
                return 42

        prop = MyClass.__dict__["value"]
        p = pin(prop)
        val = p.xray()
        self.assertEqual(val["__type__"], "property")
        self.assertIn("fget", val)
        self.assertEqual(val["fget"]["__type__"], "function")

    def test_property_fget_fset(self):
        class MyClass:
            def __init__(self):
                self._val = 0

            @property
            def value(self):
                return self._val

            @value.setter
            def value(self, v):
                self._val = v

        prop = MyClass.__dict__["value"]
        p = pin(prop)
        val = p.xray()
        self.assertEqual(val["__type__"], "property")
        self.assertIn("fget", val)
        self.assertIn("fset", val)

    def test_staticmethod(self):
        class MyClass:
            @staticmethod
            def my_static():
                return "static"

        sm = MyClass.__dict__["my_static"]
        p = pin(sm)
        val = p.xray()
        self.assertEqual(val["__type__"], "staticmethod")
        self.assertIn("__func__", val)
        self.assertEqual(val["__func__"]["__name__"], "my_static")

    def test_classmethod(self):
        class MyClass:
            @classmethod
            def my_class(cls):
                return cls

        cm = MyClass.__dict__["my_class"]
        p = pin(cm)
        val = p.xray()
        self.assertEqual(val["__type__"], "classmethod")
        self.assertIn("__func__", val)
        self.assertEqual(val["__func__"]["__name__"], "my_class")


class TestBuiltinFunctionExtraction(unittest.TestCase):
    """Tests for builtin_function_or_method extraction."""

    def test_builtin_len(self):
        p = pin(len)
        val = p.xray()
        self.assertEqual(val["__type__"], "builtin_function_or_method")
        self.assertEqual(val["__name__"], "len")

    def test_builtin_print(self):
        p = pin(print)
        val = p.xray()
        self.assertEqual(val["__type__"], "builtin_function_or_method")
        self.assertEqual(val["__name__"], "print")

    def test_builtin_abs(self):
        p = pin(abs)
        val = p.xray()
        self.assertEqual(val["__type__"], "builtin_function_or_method")
        self.assertEqual(val["__name__"], "abs")

    def test_method_of_list(self):
        lst = [1, 2, 3]
        append_method = lst.append
        p = pin(append_method)
        val = p.xray()
        self.assertEqual(val["__type__"], "builtin_function_or_method")
        self.assertEqual(val["__name__"], "append")


class TestGeneratorExtraction(unittest.TestCase):
    """Tests for generator object extraction."""

    def test_generator_basic(self):
        def gen_func():
            yield 1
            yield 2
            yield 3

        gen = gen_func()
        p = pin(gen)
        val = p.xray()
        self.assertEqual(val["__type__"], "generator")
        # Clean up generator
        gen.close()

    def test_generator_with_values(self):
        def count_up(n):
            for i in range(n):
                yield i

        gen = count_up(5)
        p = pin(gen)
        val = p.xray()
        self.assertEqual(val["__type__"], "generator")
        gen.close()


class TestEnumerateExtraction(unittest.TestCase):
    """Tests for enumerate object extraction."""

    def test_enumerate_default_start(self):
        e = enumerate([1, 2, 3])
        p = pin(e)
        val = p.xray()
        self.assertEqual(val["__type__"], "enumerate")
        self.assertEqual(val["start_index"], 0)

    def test_enumerate_custom_start(self):
        e = enumerate([1, 2, 3], start=10)
        p = pin(e)
        val = p.xray()
        self.assertEqual(val["__type__"], "enumerate")
        self.assertEqual(val["start_index"], 10)

    def test_enumerate_after_iteration(self):
        e = enumerate(["a", "b", "c"])
        next(e)  # Consume first element
        next(e)  # Consume second element
        p = pin(e)
        val = p.xray()
        self.assertEqual(val["__type__"], "enumerate")
        # Index should have advanced
        self.assertEqual(val["start_index"], 2)


if __name__ == "__main__":
    unittest.main()
