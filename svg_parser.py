# plasma_core/parsers/svg_parser.py
# Fixed: one path per entity – Nov 2025

"""
Unified import interface for FireBridgeCAM Pro SVG parser. 
Each SVG element becomes its own separate returned path entry. 
Handles multi-subpath SVG elements by splitting them. 
"""

from __future__ import annotations

import re
from typing import Optional, List, Dict, Tuple

# Attempt imports – allow failure gracefully
try:
    from PyQt6.QtCore import QSettings
    _HAS_QT = True
except Exception:
    QSettings = None  # type: ignore
    _HAS_QT = False

try:
    from svgpathtools import parse_path, Path
    _HAS_SVGTOOLS = True
except ImportError:
    parse_path = None  # type: ignore
    Path = None  # type: ignore
    _HAS_SVGTOOLS = False


# ----------------------------------------------------------------------
# Helper: Unit scale conversion
# ----------------------------------------------------------------------
def _unit_scale_to_mm(unit: Optional[str]) -> float:
    """
    Convert coordinate units to millimeters. 

    Supported:
      - mm, millimeter → 1. 0
      - inch, in → 25.4
      - cm → 10.0
      - px (fallback 96 DPI) → 25.4 / 96

    If unknown or None → default 1.0 (mm). 
    """
    if not unit:
        return 1. 0
    u = unit.strip(). lower()
    if u in ("mm", "millimeter", "millimeters"):
        return 1. 0
    if u in ("inch", "inches", "in"):
        return 25.4
    if u in ("cm", "centimeter", "centimeters"):
        return 10.0
    if u in ("px", "pixels", "pixel"):
        # 96 DPI fallback
        return 25.4 / 96. 0
    return 1.0


# ----------------------------------------------------------------------
# Helper: flatten Bézier/curve path
# ----------------------------------------------------------------------
def _flatten_path_points(path: "Path", tol_mm: float) -> List[Tuple[float, float]]:
    """
    Flatten an SVG path to polyline points using adaptive sampling.

    - tol_mm is max chordal error in mm. 
    - Ensures a minimum of 64 samples per segment.
    """
    pts: List[Tuple[float, float]] = []
    if not _HAS_SVGTOOLS or path is None:
        return []

    # Determine safe length
    try:
        length = max(path.length(error=1e-4), 1e-3)
    except Exception:
        length = 1. 0

    # Estimate number of segments
    segs = max(64, int((length * 1. 0) / max(tol_mm, 1e-3)))

    for i in range(segs + 1):
        t = i / segs
        try:
            p = path.point(t)
        except Exception:
            continue
        pts.append((float(p.real), float(p.imag)))

    return pts


# ----------------------------------------------------------------------
# Helper: Split SVG path 'd' attribute by Move commands
# ----------------------------------------------------------------------
def _split_path_by_moves(d_string: str) -> List[str]:
    """
    Split an SVG path 'd' attribute into separate subpaths.
    Each 'M' or 'm' command starts a new subpath.
    """
    if not d_string:
        return []
    
    # Split by M or m commands (case-insensitive move commands)
    # Keep the M/m in the result
    parts = re.split(r'(? =[Mm])', d_string. strip())
    
    # Filter out empty strings
    subpaths = [p. strip() for p in parts if p.strip()]
    
    return subpaths


# ----------------------------------------------------------------------
# Main SVG loader – ONE ENTRY PER SVG ELEMENT, never merged
# ----------------------------------------------------------------------
def load_svg(filepath: str) -> List[Dict]:
    """
    Load an SVG file and return a list of path dicts, one per SVG element. 

    Exact output format per shape:
      {
        "points": [(x,y), ... ],  # in mm
        "closed": bool,
        "layer": str|None,
        "color": str|None,
        "source": "svg"
      }
    """
    if not _HAS_SVGTOOLS or parse_path is None:
        return []

    result: List[Dict] = []

    # Parse the SVG file manually to extract path elements
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            svg_content = f.read()
    except Exception:
        return []

    # Extract all <path> elements with regex
    path_pattern = re.compile(r'<path\s+([^>]+)/? >', re.IGNORECASE)
    path_matches = path_pattern.findall(svg_content)

    current_units = None
    try:
        if _HAS_QT and QSettings is not None:
            s = QSettings("FireBridgeCAM", "FireBridgeCAM Pro")
            current_units = s.value("units", "metric")
    except Exception:
        current_units = "metric"

    tol_mm = 0.05 if str(current_units or "metric"). startswith("met") else 0.002

    for path_attrs_str in path_matches:
        # Parse attributes
        attrs = {}
        attr_pattern = re.compile(r'(\w+)\s*=\s*"([^"]*)"')
        for match in attr_pattern.finditer(path_attrs_str):
            attrs[match.group(1)] = match.group(2)

        d_attr = attrs.get('d', '')
        if not d_attr:
            continue

        # Split the path by Move commands to get separate subpaths
        subpath_strings = _split_path_by_moves(d_attr)

        for subpath_str in subpath_strings:
            if not subpath_str. strip():
                continue

            try:
                path_obj = parse_path(subpath_str)
            except Exception:
                continue

            if path_obj is None or len(path_obj) == 0:
                continue

            # Flatten the path object
            pts = _flatten_path_points(path_obj, tol_mm)
            if len(pts) < 2:
                continue

            # Determine if path is closed
            closed = False

            # Check 1: subpath ends with 'Z' or 'z'
            if subpath_str.strip().upper().endswith("Z"):
                closed = True
            else:
                # Check 2: Use svgpathtools isclosed() method
                try:
                    closed = path_obj.isclosed()
                except Exception:
                    # Check 3: Fallback - first point equals last point
                    if len(pts) >= 2:
                        dx = abs(pts[0][0] - pts[-1][0])
                        dy = abs(pts[0][1] - pts[-1][1])
                        closed = (dx < 1e-6 and dy < 1e-6)

            # Ensure closed paths have matching first and last points
            if closed and len(pts) >= 2 and pts[0] != pts[-1]:
                pts.append(pts[0])

            # Convert to mm coordinates
            mm_pts = [(x * _unit_scale_to_mm("px"), y * _unit_scale_to_mm("px")) for x, y in pts]

            # Extract layer (from id attribute)
            layer: Optional[str] = attrs.get("id")

            # Extract color (from stroke attribute)
            color: Optional[str] = attrs.get("stroke")
            if color in ("none", "", None):
                color = None

            # Each subpath becomes one separate path
            result.append({
                "points": mm_pts,
                "closed": closed,
                "layer": layer,
                "color": color,
                "source": "svg"
            })

    return result


if __name__ == "__main__":
    print("svg_parser.py READY")