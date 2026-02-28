from pyprobe import pin
import ctypes

# Look at a float (24 bytes, data at 16)
pin(3.14).examine()

# Look at an int (28 bytes, data at 24)
pin(100).examine()

# Look at a small string (Watch how ob_size and data look)
pin("Hi").examine()

x = [10, 20, 30]
pin(x).examine()

y = {1:"A",2:"B",3:"C"}
p = pin(y)

# Dump the Dict object header itself
p.dump_raw(p.address, length=48, label="DICT_HEADER")

# Dump the Key-Object allocation (The indices and entries)
keys_addr = ctypes.cast(p.lens.ma_keys, ctypes.c_void_p).value
p.dump_raw(keys_addr, length=128, label="KEYS_ALLOC")

p.examine()