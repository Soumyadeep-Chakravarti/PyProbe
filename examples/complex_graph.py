import sys
import os
sys.path.insert(0, os.path.abspath("src"))
from pyprobe import pin

def complex_graph_tour():
    """Showcase PyProbe on a complex, messy object graph."""
    
    # Node in a doubly linked list
    class Node:
        def __init__(self, val):
            self.val = val
            self.prev = None
            self.next = None
            self.data = bytearray(b"some mutable data")

    n1 = Node(1)
    n2 = Node(2)
    n1.next = n2
    n2.prev = n1
    
    # A self-reference via a dictionary
    metadata = {"node": n1, "tags": {"core", "graph"}}
    n1.meta = metadata
    
    # A set with some interned and non-interned objects
    collection = {n1, n2, "stable_string", (1, 2)}
    
    print("\n[ X-RAY OF DOUBLY LINKED LIST NODE ]")
    p = pin(n1)
    p.examine()
    
    print("\n[ PULLING DATA FOR THE WHOLE GRAPH ]")
    # This should show cycles as hex addresses
    abstract = p.pull_data_from_address(p.address)
    print(f"Abstract Graph: {abstract}")

if __name__ == "__main__":
    complex_graph_tour()
