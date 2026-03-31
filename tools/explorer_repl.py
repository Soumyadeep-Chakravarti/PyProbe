import sys
import os
import ctypes
import ast

sys.path.insert(0, os.path.abspath("src"))
from pyprobe import pin
from pyprobe.core.pointer.engine import Pointer


# Safe built-in functions allowed in REPL evaluation
_SAFE_BUILTINS = {
    "True": True,
    "False": False,
    "None": None,
    "int": int,
    "float": float,
    "str": str,
    "bytes": bytes,
    "list": list,
    "tuple": tuple,
    "dict": dict,
    "set": set,
    "frozenset": frozenset,
    "len": len,
    "range": range,
    "abs": abs,
    "min": min,
    "max": max,
    "sum": sum,
    "sorted": sorted,
    "reversed": reversed,
    "enumerate": enumerate,
    "zip": zip,
    "map": map,
    "filter": filter,
}


def safe_eval(expr: str, context: dict):
    """Safely evaluate a Python expression.

    Only allows literal values and safe built-in operations.
    Does NOT allow arbitrary code execution, imports, or attribute access
    to potentially dangerous objects.

    Args:
        expr: The expression string to evaluate.
        context: A dictionary of variable names available in evaluation.

    Returns:
        The evaluated result.

    Raises:
        ValueError: If the expression contains unsafe operations.
    """
    # First, try to parse as a literal (safest option)
    try:
        return ast.literal_eval(expr)
    except (ValueError, SyntaxError):
        pass

    # For non-literals, parse the AST and validate
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"Invalid syntax: {e}")

    # Validate the AST - only allow safe node types
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise ValueError("Imports are not allowed")
        if isinstance(node, ast.Call):
            # Allow calls only to safe builtins
            if isinstance(node.func, ast.Name):
                if node.func.id not in _SAFE_BUILTINS:
                    raise ValueError(f"Function '{node.func.id}' is not allowed")
            elif isinstance(node.func, ast.Attribute):
                # Allow method calls on basic types (e.g., "hello".upper())
                pass
            else:
                raise ValueError("Complex function calls are not allowed")
        if isinstance(node, ast.Attribute):
            # Block access to dunder attributes
            if node.attr.startswith("_"):
                raise ValueError(f"Access to '{node.attr}' is not allowed")

    # Create a restricted globals dict
    safe_globals = {"__builtins__": _SAFE_BUILTINS}
    safe_globals.update(context)

    return eval(compile(tree, "<repl>", "eval"), safe_globals, context)


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
    print("=" * 60)
    print("Welcome to PyProbe Live Memory Explorer".center(60))
    print("=" * 60)
    help_msg()

    # We can use a reference object to get an engine instance
    _dummy = Pointer(target=1)

    context = {}

    while True:
        try:
            cmd = input("\n>>> ").strip().split(None, 1)
            if not cmd:
                continue

            action = cmd[0].lower()

            if action == "exit":
                break

            if action == "snapshot":
                try:
                    expr = cmd[1]
                    # Use safe_eval instead of dangerous eval()
                    obj = safe_eval(expr, context)
                    p = pin(obj)
                    p.examine()
                    # Store the result with a safe key
                    var_name = expr.split(".")[0].split("[")[0].split("(")[0]
                    if var_name.isidentifier():
                        context[var_name] = obj
                except ValueError as e:
                    print(f"Safety Error: {e}")
                except Exception as e:
                    print(f"Eval Error: {e}")

            elif action in ["identify", "examine"]:
                try:
                    addr_str = cmd[1]
                    addr = int(addr_str, 16)

                    if action == "identify":
                        val = _dummy.pull_data_from_address(addr)
                        print(f"Address {addr_str} identified as: {repr(val)}")
                    else:
                        # For examine, we'd need an actual object handle?
                        # No, we can try to guess from the engine if we implement address-based examine
                        # Let's fallback to identify for now as examine depends on target handle
                        print(
                            "X-Ray from arbitrary address requires knowing the target handle in current Pointer impl."
                        )
                        print(
                            f"Identified Result: {_dummy.pull_data_from_address(addr)}"
                        )
                except Exception as e:
                    print(f"Address Error: {e}")
            else:
                help_msg()

        except EOFError:
            break
        except Exception as e:
            print(f"REPL Error: {e}")


if __name__ == "__main__":
    repl()
