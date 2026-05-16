from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from openclaw_engineering.tools.airfoil import naca4_coords
from openclaw_engineering.sculpt.mesh_common import loft_sections, write_stl


def build(params: dict[str, Any], out_stl: Path, **kwargs: Any) -> Path:
    span = float(params.get("span_mm", 1200))
    nsec = int(params.get("section_count", 12))
    chord_root = float(params.get("chord_root_mm", 320))
    chord_tip = float(params.get("chord_tip_mm", 180))
    twist_tip = math.radians(float(params.get("twist_tip_deg", -2)))
    camber_bias = float(params.get("camber_bias", 0))
    thick_bias = float(params.get("thickness_bias", 0))
    m, p, t = 0.02 + camber_bias * 0.02, 0.4 + camber_bias * 0.15, 0.12 + thick_bias * 0.04
    base = naca4_coords(m, max(0.1, min(0.9, p)), max(0.08, min(0.25, t)))

    sections: list[list[tuple[float, float, float]]] = []
    for i in range(nsec):
        eta = i / max(nsec - 1, 1)
        y = -span / 2 + eta * span
        chord = chord_root + (chord_tip - chord_root) * eta
        twist = twist_tip * eta
        ring = []
        for x, z in base:
            px = x * chord
            pz = z * chord
            cx = math.cos(twist) * px - math.sin(twist) * pz
            cz = math.sin(twist) * px + math.cos(twist) * pz
            ring.append((cx, y, cz))
        sections.append(ring)

    tris = loft_sections(sections)
    z_shift = float(params.get("mount_offset_z_mm", params.get("mount_offset_mm", 0)))
    if z_shift:
        tris = [tuple((a, b, c + z_shift) for a, b, c in tri) for tri in tris]
    write_stl(tris, out_stl)
    return out_stl
