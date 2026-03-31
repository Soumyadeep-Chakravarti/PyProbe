"""Core pointer module for memory introspection.

This module provides the Pointer class which wraps Python objects
and enables low-level memory access and inspection.
"""

from .engine import Pointer

__all__ = ["Pointer"]
