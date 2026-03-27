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

def test_industrial():
    # 1. Dict with tombstones
    d = {i: i for i in range(5)}
    del d[2]
    run_test("Dict w/ Deletions", d)

    # 2. Sets
    s = {10, 20, 30}
    run_test("Set", s)

    # 3. Bytes
    b = b"hello\x00world"
    run_test("Bytes", b)

if __name__ == "__main__":
    test_industrial()
