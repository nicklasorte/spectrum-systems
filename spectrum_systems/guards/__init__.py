"""Lightweight guard utilities.

This package intentionally avoids eager submodule imports so guard scripts
can pull only the helpers they directly require, without dragging in the
runtime package or its third-party dependencies (e.g. ``jsonschema``).
"""

__all__: list[str] = []
