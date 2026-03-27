import ctypes

class Node:
    pass

n = Node()
n.x = 10
n.y = 20
obj_addr = id(n)
dict_addr = id(n.__dict__)

print(f"Object: {hex(obj_addr)}")
print(f"Dict:   {hex(dict_addr)}")

data = ctypes.string_at(obj_addr, 64)
# Look for dict_addr in the object bytes
for i in range(0, 56, 8):
    val = ctypes.c_void_p.from_address(obj_addr + i).value
    if val == dict_addr:
        print(f"Found Dict address at offset +{i}")
