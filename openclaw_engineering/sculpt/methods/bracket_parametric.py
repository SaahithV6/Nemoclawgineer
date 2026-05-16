from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from openclaw_engineering.sculpt.mesh_common import box_tris, write_stl


def build(params: dict[str, Any], out_stl: Path, **kwargs: Any) -> Path:
    style = params.get("style", "L")
    ta = float(params.get("thickness_mm", 8))
    la = float(params.get("leg_a_mm", 80))
    lb = float(params.get("leg_b_mm", 60))
    angle = math.radians(float(params.get("bend_angle_deg", 90)))
    join = params.get("join_pattern", "gusseted")
    tris: list[tuple[tuple[float, float, float], ...]] = []

    if str(style).upper() == "T":
        tris.extend(box_tris(0, 0, 0, la, ta, lb))
        tris.extend(box_tris(la / 2 - ta / 2, 0, lb, ta, la, ta))
    else:
        tris.extend(box_tris(0, 0, 0, la, ta, ta))
        tris.extend(box_tris(la, 0, 0, lb * math.cos(angle), ta, max(lb * math.sin(angle), ta)))

    fillet = float(params.get("fillet_radius_mm", 0))
    if fillet > 0 and join in ("organic_blend", "gusseted", "filleted"):
        tris.extend(box_tris(la - fillet, 0, 0, fillet * 1.4, ta * 1.2, fillet * 1.4))
    if join == "gusseted":
        gs = float(params.get("gusset_size_mm", min(la, lb) * 0.35))
        tris.extend(box_tris(la - gs, 0, 0, gs, ta, gs))

    write_stl(tris, out_stl)
    return out_stl
