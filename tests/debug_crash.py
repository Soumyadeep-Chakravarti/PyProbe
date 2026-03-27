import sys
import os
sys.path.insert(0, os.path.abspath("src"))
from pyprobe import pin

def debug_dict_crash():
    print("Case 1: String keys")
    d1 = {"a": 1, "b": 2}
    print(pin(d1).pull_data_from_address(id(d1)))

    print("\nCase 2: Mixed keys (Manual iteration)")
    d2 = {1: "a", 2.5: "b", (1,2): "c"}
    p = pin(d2)
    addr = id(d2)
    
    # Try pulling keys individually first
    print("Pulling key 1 (Int):", p.pull_data_from_address(id(1)))
    print("Pulling key 2.5 (Float):", p.pull_data_from_address(id(2.5)))
    print("Pulling key (1,2) (Tuple):", p.pull_data_from_address(id((1,2))))
    
    print("\nPulling whole dict...")
    print(p.pull_data_from_address(addr))

if __name__ == "__main__":
    debug_dict_crash()
