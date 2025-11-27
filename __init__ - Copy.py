# plasma_core/parsers/__init__.py
"""
FireBridgeCAM Pro CAD File Parsers
Graceful imports with fallback support
"""

from __future__ import annotations
from typing import List, Dict

# DXF Parser
try:
    from . dxf_parser import load_dxf
    _HAS_DXF = True
except Exception:
    _HAS_DXF = False
    def load_dxf(filename: str, units: str = "mm") -> List[Dict]:
        """Fallback when ezdxf not installed"""
        return []

# SVG Parser
try:
    from .svg_parser import load_svg
    _HAS_SVG = True
except Exception:
    _HAS_SVG = False
    def load_svg(filepath: str) -> List[Dict]:
        """Fallback when svgpathtools not installed"""
        return []

__all__ = ["load_dxf", "load_svg"]