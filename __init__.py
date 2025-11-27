# plasma_core/__init__.py
# This file makes plasma_core a real Python package

# Re-export the parser functions so main.py can do: from plasma_core.parsers import load_dxf, load_svg
from .parsers import load_dxf, load_svg

__all__ = ["load_dxf", "load_svg"]