import sys
import os
from typing import Any, Dict, Optional, Set, TYPE_CHECKING

sys.path.insert(0, os.path.abspath("src"))
from pyprobe import pin

if TYPE_CHECKING:
    from pyprobe.core.pointer.engine import Pointer

def complex_graph_tour():
    """Showcase PyProbe on a complex, messy object graph."""
    
    # Node in a doubly linked list
    class Node:
        def __init__(self, val: int) -> None:
            self.val: int = val
            self.prev: Optional["Node"] = None
            self.next: Optional["Node"] = None
            self.data: bytearray = bytearray(b"some mutable data")
            self.meta: Dict[str, Any] = {}

    n1 = Node(1)
    n2 = Node(2)
    n1.next = n2
    n2.prev = n1
    
    # A self-reference via a dictionary
    metadata: Dict[str, Any] = {"node": n1, "tags": {"core", "graph"}}
    n1.meta = metadata
    
    # A set with some interned and non-interned objects
    collection: Set[Any] = {n1, n2, "stable_string", (1, 2)}
    
    print("\n[ X-RAY OF DOUBLY LINKED LIST NODE ]")
    p: "Pointer" = pin(n1)  # type: ignore[attr-defined]
    p.examine()
    
    print("\n[ PULLING DATA FOR THE WHOLE GRAPH ]")
    # This should show cycles as hex addresses
    abstract = p.pull_data_from_address(p.address)
    print(f"Abstract Graph: {abstract}")
    
    # Use collection to verify the graph structure
    print(f"\nCollection contains {len(collection)} items")

if __name__ == "__main__":
    complex_graph_tour()
