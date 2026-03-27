import sys, os
sys.path.insert(0, os.path.abspath("src"))
from pyprobe.core.pointer.engine import Pointer

def run_test(name, obj):
    try:
        print(f"--- TEST: {name} ---")
        p = Pointer(obj)
        val = p.pull_data_from_address(p.address)
        print(f"Obj: {repr(obj)}")
        print(f"Pulled: {repr(val)}")
        p.examine()
        print("-" * 20)
    except Exception as e:
        print(f"FAILED TEST {name}: {e}")
        import traceback
        traceback.print_exc()

def test_lens_restoration():
    # Test a few types to ensure lenses are picking up data correctly
    run_test("Int", 123456789)
    run_test("Float", 3.14159)
    run_test("String", "Hello Lenses")
    run_test("List", [1, 2, [3, 4]])
    run_test("Dict", {"a": 1, "b": {"c": 2}})

if __name__ == "__main__":
    test_lens_restoration()
