"""
PyProbe UX Module
=================
Phase 1: Human-friendly introspection and reporting.

Provides explain(), audit(), to_dict()/to_json(), and compare()
for ergonomic exploration of mutation targets.
"""

import os
import sys
import json
import ctypes
import inspect
import gc
from typing import Any, Dict, List, Tuple, Optional, Literal
from dataclasses import dataclass, field, asdict
from enum import Enum

from pyprobe.core.Scalpel import is_safe_to_mutate, SMALL_INT_ADDRS, SMALL_INT_MIN, SMALL_INT_MAX
from pyprobe.core.offset_discovery import LIST_ITEMS_OFFSET, DICT_LAYOUT, STR_DATA_OFFSET
from pyprobe.core.common import (
    PyProbeError,
    PyProbeSafetyError,
    PyProbeSecurityError,
    PyProbeIntegrityError,
)


# ── Color Support ───────────────────────────────────────────────────────────

class _Color:
    """ANSI escape sequences for terminal output."""
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"

    # Colorblind-safe palette
    CB_BLUE   = "\033[94m"
    CB_ORANGE = "\033[38;5;208m"
    CB_GREEN  = "\033[32m"

    @classmethod
    def enabled(cls) -> bool:
        mode = os.environ.get("PYPROBE_COLOR", "auto").lower()
        if mode == "always":
            return True
        if mode == "never":
            return False
        # auto: enabled if stdout is a TTY
        return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

    @classmethod
    def colorblind(cls) -> bool:
        return os.environ.get("PYPROBE_COLOR_MODE", "normal").lower() == "colorblind"

    @classmethod
    def c(cls, text: str, color: str) -> str:
        if not cls.enabled():
            return text
        return f"{color}{text}{cls.RESET}"


# ── Data Classes ────────────────────────────────────────────────────────────

class SafetyVerdict(Enum):
    SAFE = "safe"
    UNSAFE = "unsafe"


@dataclass
class MutationTarget:
    """Structured description of a mutation candidate."""
    object_type: str
    object_repr: str
    memory_address: int
    size_bytes: int
    verdict: SafetyVerdict
    reason: str
    mutation_function: str
    constraints: List[str] = field(default_factory=list)


@dataclass
class AuditReport:
    """Full audit report for a scope."""
    targets: List[MutationTarget]
    total_safe: int = 0
    total_unsafe: int = 0


# ── Core Functions ───────────────────────────────────────────────────────────

def _estimate_size(obj: Any) -> int:
    """Rough byte size of a Python object."""
    if isinstance(obj, (int, float, bool)):
        return sys.getsizeof(obj)
    if isinstance(obj, str):
        return sys.getsizeof(obj)
    if isinstance(obj, bytes):
        return sys.getsizeof(obj)
    if isinstance(obj, (list, tuple)):
        return sys.getsizeof(obj) + len(obj) * 8
    if isinstance(obj, dict):
        return sys.getsizeof(obj) + len(obj) * 80
    return sys.getsizeof(obj)


def _mutation_function_name(obj: Any) -> str:
    """Map an object type to the corresponding Scalpel function name."""
    if isinstance(obj, float):
        return "mutate_float"
    if isinstance(obj, int):
        return "mutate_int"
    if isinstance(obj, list):
        return "safe_list_swap"
    if isinstance(obj, dict):
        return "safe_dict_value_swap"
    if isinstance(obj, bytes):
        return "mutate_bytes"
    if isinstance(obj, str):
        return "mutate_str"
    return "unsupported"


def _get_constraints(obj: Any) -> List[str]:
    """List mutation constraints for an object."""
    constraints = []
    if isinstance(obj, int):
        constraints.append(f"New value must fit in {len(obj.to_bytes((obj.bit_length() + 7) // 8 or 1, 'big', signed=True))} digit(s)")
        if SMALL_INT_MIN <= obj <= SMALL_INT_MAX:
            constraints.append("Cached integer: cannot mutate in-place (immutable cache)")
    if isinstance(obj, (float,)):
        constraints.append("New value must be a finite float")
    if isinstance(obj, (str, bytes)):
        constraints.append(f"New value must be exactly {len(obj)} bytes/chars")
        if isinstance(obj, str):
            state_flags = ctypes.c_uint32.from_address(id(obj) + 32).value
            encoding = (state_flags >> 2) & 0x07
            if encoding != 1:
                constraints.append("Only Compact ASCII encoding supported")
            if (state_flags & 0x03) != 0:
                constraints.append("String is interned: immutable")
    if isinstance(obj, list):
        constraints.append(f"Index must be 0..{len(obj) - 1}")
    if isinstance(obj, dict):
        constraints.append(f"Key must exist: {list(obj.keys())[:5]}{'...' if len(obj) > 5 else ''}")
    return constraints


def explain(obj: Any) -> str:
    """
    Generate a human-readable mutation plan for a single object.

    Returns a formatted string describing:
    - What the object is
    - Where it lives in memory
    - Whether it can be mutated
    - How to mutate it
    - What constraints apply
    """
    safe, reason = is_safe_to_mutate(obj, stack_depth=5)
    verdict = SafetyVerdict.SAFE if safe else SafetyVerdict.UNSAFE
    fn_name = _mutation_function_name(obj)
    constraints = _get_constraints(obj)
    size = _estimate_size(obj)

    lines = []
    c = _Color

    # Header
    type_name = type(obj).__name__
    repr_str = repr(obj)
    if len(repr_str) > 60:
        repr_str = repr_str[:57] + "..."
    lines.append(c.c(f"  {type_name}", c.BOLD) + f"  {c.c(repr_str, c.DIM)}")
    lines.append(f"  Address:  0x{id(obj):012x}")
    lines.append(f"  Size:     ~{size} bytes")
    lines.append("")

    # Verdict
    if verdict == SafetyVerdict.SAFE:
        lines.append(f"  Verdict:  {c.c('SAFE', c.GREEN)}")
        lines.append(f"  Reason:   {reason}")
    else:
        lines.append(f"  Verdict:  {c.c('UNSAFE', c.RED)}")
        lines.append(f"  Reason:   {reason}")
    lines.append("")

    # Mutation function
    if fn_name != "unsupported":
        lines.append(f"  Function: {c.c(fn_name, c.CYAN)}")
    else:
        lines.append(f"  Function: {c.c('none (unsupported type)', c.YELLOW)}")

    # Constraints
    if constraints:
        lines.append(f"  Constraints:")
        for con in constraints:
            lines.append(f"    - {c.c(con, c.DIM)}")

    # Example code
    lines.append("")
    if fn_name == "safe_list_swap":
        lines.append(f"  Example:")
        lines.append(f"    from pyprobe import safe_list_swap")
        lines.append(f"    safe_list_swap(my_list, index, new_value)")
    elif fn_name == "safe_dict_value_swap":
        lines.append(f"  Example:")
        lines.append(f"    from pyprobe import safe_dict_value_swap")
        lines.append(f"    safe_dict_value_swap(my_dict, key, new_value)")
    elif fn_name != "unsupported":
        lines.append(f"  Example:")
        lines.append(f"    from pyprobe import {fn_name}")
        lines.append(f"    {fn_name}(target, new_value)")
    else:
        lines.append(f"  No direct mutation function available.")

    return "\n".join(lines)


def audit(scope: Optional[Dict[str, Any]] = None) -> AuditReport:
    """
    Scan a scope (dict of {name: obj}) for mutation candidates.

    If scope is None, scans the caller's local namespace via frame inspection.
    Returns an AuditReport with categorized targets.
    """
    if scope is None:
        # Walk up the call stack to find the caller's locals
        frame = inspect.currentframe()
        if frame and frame.f_back:
            scope = frame.f_back.f_locals
        else:
            scope = {}
        # Clean up frame reference
        del frame

    targets = []
    for name, obj in scope.items():
        if name.startswith("_"):
            continue
        fn = _mutation_function_name(obj)
        if fn == "unsupported":
            continue
        safe, reason = is_safe_to_mutate(obj, stack_depth=6)
        verdict = SafetyVerdict.SAFE if safe else SafetyVerdict.UNSAFE
        constraints = _get_constraints(obj)
        targets.append(MutationTarget(
            object_type=type(obj).__name__,
            object_repr=repr(obj)[:60],
            memory_address=id(obj),
            size_bytes=_estimate_size(obj),
            verdict=verdict,
            reason=reason,
            mutation_function=fn,
            constraints=constraints,
        ))

    total_safe = sum(1 for t in targets if t.verdict == SafetyVerdict.SAFE)
    total_unsafe = sum(1 for t in targets if t.verdict == SafetyVerdict.UNSAFE)

    return AuditReport(
        targets=targets,
        total_safe=total_safe,
        total_unsafe=total_unsafe,
    )


def audit_str(scope: Optional[Dict[str, Any]] = None) -> str:
    """Human-readable string version of audit()."""
    report = audit(scope)
    c = _Color
    lines = []
    lines.append(c.c("PyProbe Audit Report", c.BOLD))
    lines.append(f"  Safe:   {c.c(str(report.total_safe), c.GREEN)}")
    lines.append(f"  Unsafe: {c.c(str(report.total_unsafe), c.RED)}")
    lines.append("")

    for t in report.targets:
        verdict_color = c.GREEN if t.verdict == SafetyVerdict.SAFE else c.RED
        lines.append(f"  {c.c(t.object_type, c.BOLD)}  {c.c(t.object_repr, c.DIM)}")
        lines.append(f"    Verdict:  {c.c(t.verdict.value.upper(), verdict_color)}  ({t.reason})")
        lines.append(f"    Function: {c.c(t.mutation_function, c.CYAN)}")
        if t.constraints:
            for con in t.constraints[:2]:
                lines.append(f"    Note:     {c.c(con, c.DIM)}")
        lines.append("")

    if not report.targets:
        lines.append(f"  {c.c('No mutation targets found.', c.DIM)}")

    return "\n".join(lines)


def to_dict(obj: Any) -> Dict[str, Any]:
    """
    Structured dictionary representation of mutation metadata for an object.
    """
    safe, reason = is_safe_to_mutate(obj, stack_depth=5)
    return {
        "type": type(obj).__name__,
        "repr": repr(obj)[:120],
        "address": hex(id(obj)),
        "size_bytes": _estimate_size(obj),
        "safe_to_mutate": safe,
        "reason": reason,
        "mutation_function": _mutation_function_name(obj),
        "constraints": _get_constraints(obj),
    }


def to_json(obj: Any, indent: int = 2) -> str:
    """
    JSON string of mutation metadata.
    """
    return json.dumps(to_dict(obj), indent=indent)


def compare(obj_a: Any, obj_b: Any) -> Dict[str, Any]:
    """
    Compare two objects for mutation equivalence.

    Checks if swapping obj_a's memory with obj_b's would produce valid results.
    """
    a_safe, a_reason = is_safe_to_mutate(obj_a, stack_depth=5)
    b_safe, b_reason = is_safe_to_mutate(obj_b, stack_depth=5)
    a_fn = _mutation_function_name(obj_a)
    b_fn = _mutation_function_name(obj_b)

    type_match = type(obj_a) is type(obj_b)
    size_match = len(obj_a) == len(obj_b) if hasattr(obj_a, "__len__") and hasattr(obj_b, "__len__") else False

    compatible = type_match and a_safe and b_safe

    result = {
        "type_a": type(obj_a).__name__,
        "type_b": type(obj_b).__name__,
        "type_match": type_match,
        "size_match": size_match if type_match else None,
        "safe_a": a_safe,
        "safe_b": b_safe,
        "reason_a": a_reason,
        "reason_b": b_reason,
        "function_a": a_fn,
        "function_b": b_fn,
        "compatible": compatible,
    }

    if type_match and size_match:
        # Both must use the same function
        if a_fn == b_fn:
            result["note"] = f"Both are {a_fn} targets — swap is possible"
        else:
            result["note"] = "Type match but mutation functions differ"
    elif not type_match:
        result["note"] = "Cannot swap objects of different types"
    elif not size_match:
        result["note"] = "Cannot swap objects of different sizes"

    return result


def compare_str(obj_a: Any, obj_b: Any) -> str:
    """Human-readable comparison."""
    c = _Color
    r = compare(obj_a, obj_b)
    lines = []
    lines.append(c.c("PyProbe Compare", c.BOLD))
    lines.append(f"  Object A:  {c.c(r['type_a'], c.CYAN)}  {repr(obj_a)[:40]}")
    lines.append(f"  Object B:  {c.c(r['type_b'], c.CYAN)}  {repr(obj_b)[:40]}")
    lines.append(f"  Type match:   {'Yes' if r['type_match'] else 'No'}")
    if r['size_match'] is not None:
        lines.append(f"  Size match:   {'Yes' if r['size_match'] else 'No'}")
    lines.append(f"  Safe A:       {'Yes' if r['safe_a'] else 'No'} ({r['reason_a']})")
    lines.append(f"  Safe B:       {'Yes' if r['safe_b'] else 'No'} ({r['reason_b']})")

    compat_color = c.GREEN if r['compatible'] else c.RED
    lines.append(f"  Compatible:   {c.c(str(r['compatible']), compat_color)}")
    lines.append(f"  Note:         {c.c(r.get('note', ''), c.DIM)}")

    return "\n".join(lines)
