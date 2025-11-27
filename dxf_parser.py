# plasma_core/parsers/dxf_parser. py
# Fixed: one path per entity – Nov 2025
from __future__ import annotations

import math
from typing import List, Dict, Tuple

try:
    import ezdxf
    _HAS_EZDXF = True
except ImportError:
    ezdxf = None  # type: ignore
    _HAS_EZDXF = False


def _unit_scale_to_mm(units: str) -> float:
    if not units:
        return 1. 0
    u = units.strip().lower()
    if u. startswith("in"):
        return 25.4
    return 1.0


def _flatten_entity(entity, tol: float) -> List[Tuple[float, float]]:
    pts: List[Tuple[float, float]] = []
    
    # Try flattening first
    try:
        for x, y, *_ in entity. flattening(tol):
            pts.append((float(x), float(y)))
        if pts:
            return pts
    except Exception:
        pts = []

    # Fallback to entity-specific handling
    try:
        t = entity. dxftype()
    except Exception:
        return []

    try:
        if t == "LINE":
            s, e = entity. dxf.start, entity.dxf.end
            return [(float(s.x), float(s.y)), (float(e. x), float(e.y))]
        
        if t == "ARC":
            c, r = entity.dxf.center, float(entity.dxf.radius)
            a1, a2 = float(entity.dxf.start_angle), float(entity.dxf.end_angle)
            if a2 < a1:
                a2 += 360
            sw = a2 - a1
            n = max(12, int(sw / max(tol, 1e-4)))
            out = []
            for i in range(n + 1):
                ang = math.radians(a1 + sw * i / n)
                out.append((c. x + r * math.cos(ang), c.y + r * math.sin(ang)))
            return [(float(x), float(y)) for x, y in out]
        
        if t == "CIRCLE":
            c, r = entity. dxf.center, float(entity.dxf.radius)
            n = 64
            out = []
            for i in range(n + 1):
                ang = 2 * math.pi * i / n
                out.append((c.x + r * math. cos(ang), c.y + r * math.sin(ang)))
            return [(float(x), float(y)) for x, y in out]
        
        if t == "ELLIPSE":
            tool = entity.construction_tool()
            n = 64
            out = [(pt[0], pt[1]) for pt in tool.approximate(n)]
            return [(float(x), float(y)) for x, y in out]
        
        if t == "SPLINE":
            tool = entity. construction_tool()
            n = 128
            out = []
            for i in range(n + 1):
                try:
                    pt = tool.evaluate(i / n)
                except Exception:
                    continue
                out.append((pt[0], pt[1]))
            if out:
                return [(float(x), float(y)) for x, y in out]
            # Fallback to control points
            cp = []
            try:
                for p in entity.control_points:
                    cp. append((float(p[0]), float(p[1])))
            except Exception:
                pass
            return cp
        
        if t in ("LWPOLYLINE", "POLYLINE"):
            out = []
            try:
                for x, y, *_ in entity.flattening(tol):
                    out.append((x, y))
            except Exception:
                pass
            if out:
                return [(float(x), float(y)) for x, y in out]
            # Fallback to vertices
            try:
                for v in entity:
                    try:
                        loc = v.dxf.location
                        out.append((loc.x, loc.y))
                    except Exception:
                        pass
            except Exception:
                pass
            return [(float(x), float(y)) for x, y in out]
    except Exception:
        return []

    return []


def load_dxf(filename: str, units: str = "mm") -> List[Dict]:
    if not _HAS_EZDXF or ezdxf is None:
        return []

    paths: List[Dict] = []

    scale = _unit_scale_to_mm(units)
    tol = 0.25 / scale

    try:
        doc = ezdxf.readfile(filename)
        msp = doc.modelspace()
    except Exception:
        return []

    for e in msp:
        try:
            t = e.dxftype()
        except Exception:
            continue

        pts = _flatten_entity(e, tol)
        if len(pts) < 2:
            continue

        # Determine if closed based on entity type and geometry
        closed = False

        # Circles and ellipses are always closed
        if t in ("CIRCLE", "ELLIPSE"):
            closed = True
            # Ensure last point equals first for closed shapes
            if pts[0] != pts[-1]:
                pts.append(pts[0])
        # Check polyline closed flag
        elif t in ("LWPOLYLINE", "POLYLINE"):
            try:
                closed = bool(e.dxf.flags & 1)  # Bit 0 = closed flag
            except Exception:
                # Fallback: check if first and last points are the same
                closed = (pts[0] == pts[-1])
            if closed and pts[0] != pts[-1]:
                pts.append(pts[0])
        # Splines can be closed
        elif t == "SPLINE":
            try:
                closed = bool(e.closed)
            except Exception:
                closed = (pts[0] == pts[-1])
            if closed and pts[0] != pts[-1]:
                pts.append(pts[0])
        # For other entities, check geometry
        else:
            closed = (pts[0] == pts[-1])

        try:
            layer = str(e.dxf.layer)
        except Exception:
            layer = "0"

        try:
            col = int(e.dxf.color)
            color = str(col) if col > 0 else None
        except Exception:
            color = None

        scaled_pts = [(x * scale, y * scale) for x, y in pts]

        # Each entity becomes one separate path
        paths.append(
            {
                "points": [(float(x), float(y)) for x, y in scaled_pts],
                "closed": closed,
                "layer": layer,
                "color": color,
                "source": "dxf",
            }
        )

    return paths


if __name__ == "__main__":
    print("dxf_parser.py READY")