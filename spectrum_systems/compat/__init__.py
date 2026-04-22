"""Backward compatibility layer for 3LS simplification (Phase 8).

Maps old system names → new consolidated system names.
Old code continues to work during migration window.
"""

from spectrum_systems.compat.deprecation_layer import DeprecationLayer

__all__ = ["DeprecationLayer"]
