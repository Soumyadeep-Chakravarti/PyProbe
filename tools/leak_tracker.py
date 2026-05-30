import sys
import os
import ctypes
import gc
import time
from typing import Any

sys.path.insert(0, os.path.abspath("src"))
from pyprobe import pin

class RefCountTracker:
    def __init__(self, obj: Any) -> None:
        self._target: Any = obj
        self._addr: int = id(obj)
        self._initial_refcnt: int = pin(obj).header.ob_refcnt
        self._history: list[tuple[float, int]] = [(0, self._initial_refcnt)]

    def snapshot(self, label: str = "") -> None:
        # We need to manually read the refcnt from the address
        # but avoid creating new refs if possible (pin creates some)
        # Actually, pin(obj) creates temporary refs.
        # Let's read it directly from the memory to see the 'True' count.
        true_refcnt: int = ctypes.c_ssize_t.from_address(self._addr).value
        # Subtract our tracker's hold (self._target)
        # But wait, we ARE using the object here.
        # Standard sys.getrefcount(obj) includes its own call ref.
        # Let's just track the raw number over time.
        self._history.append((time.time(), true_refcnt))
        print(f"[{label}] Address {hex(self._addr)} | Current RefCount: {true_refcnt}")

    def show_delta(self) -> None:
        print("\n--- REFCOUNT SNAPSHOT DELTA ---")
        start_time, start_cnt = self._history[0]
        end_time, end_cnt = self._history[-1]
        delta = end_cnt - start_cnt
        print(f"Start: {start_cnt} | Current: {end_cnt} | Delta: {delta:+} over {end_time - start_time:.4f}s")
        if delta > 0:
            print("ALERT: Possible Reference Leak Detected!")

def test_leak_tracking() -> None:
    # Setup
    print("Initializing Leak Tracker...")
    data: dict[str, Any] = {"secret": "data"}
    tracker = RefCountTracker(data)
    tracker.snapshot("Initial")

    # Simulate leaks
    print("\nAdding to global leak list...")
    leak_list: list[Any] = []
    leak_list.append(data)
    tracker.snapshot("After Link")

    # Simulate deeper cycles
    print("\nCreating self-reference...")
    data['self'] = data
    tracker.snapshot("After Self-Ref")

    # Report
    tracker.show_delta()

if __name__ == "__main__":
    test_leak_tracking()
