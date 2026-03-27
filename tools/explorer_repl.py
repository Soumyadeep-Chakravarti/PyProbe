import sys
import os
import ctypes

sys.path.insert(0, os.path.abspath("src"))
from pyprobe import pin
from pyprobe.core.pointer.engine import Pointer

def help_msg():
    print("""
    PyProbe: Live Memory REPL
    commands:
      identify <addr>  : Extract logical data from hex address
      examine <addr>   : Full memory X-Ray of address
      snapshot <val>   : Pin a value by name and examine it
      exit             : Exit REPL
    """)

def repl():
    print("="*60)
    print("Welcome to PyProbe Live Memory Explorer".center(60))
    print("="*60)
    help_msg()
    
    # We can use a reference object to get an engine instance
    _dummy = Pointer(1)
    
    context = {}
    
    while True:
        try:
            cmd = input("\n>>> ").strip().split(None, 1)
            if not cmd: continue
            
            action = cmd[0].lower()
            
            if action == 'exit': break
            
            if action == 'snapshot':
                try:
                    expr = cmd[1]
                    # Evaluate the expression in current context to get an object
                    obj = eval(expr, globals(), context)
                    p = pin(obj)
                    p.examine()
                    context[expr.split('.')[0]] = obj
                except Exception as e:
                    print(f"Eval Error: {e}")
                    
            elif action in ['identify', 'examine']:
                try:
                    addr_str = cmd[1]
                    addr = int(addr_str, 16)
                    
                    if action == 'identify':
                        val = _dummy.pull_data_from_address(addr)
                        print(f"Address {addr_str} identified as: {repr(val)}")
                    else:
                        # For examine, we'd need an actual object handle?
                        # No, we can try to guess from the engine if we implement address-based examine
                        # Let's fallback to identify for now as examine depends on target handle
                        print("X-Ray from arbitrary address requires knowing the target handle in current Pointer impl.")
                        print(f"Identified Result: {_dummy.pull_data_from_address(addr)}")
                except Exception as e:
                    print(f"Address Error: {e}")
            else:
                help_msg()
                
        except EOFError: break
        except Exception as e:
            print(f"REPL Error: {e}")

if __name__ == "__main__":
    repl()
