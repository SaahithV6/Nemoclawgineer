from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from openclaw_engineering.sculpt.mesh_common import sdf_to_stl


def build(params: dict[str, Any], out_stl: Path, **kwargs: Any) -> Path:
    res = int(params.get("resolution", 48))
    prims = params.get("primitives") or [
        {"shape": "sphere", "center": [0, 0, 0], "size": [80, 80, 80], "blend_radius": 15},
        {"shape": "box", "center": [60, 0, 0], "size": [100, 40, 40], "blend_radius": 10},
    ]

    def smin(a: float, b: float, k: float) -> float:
        if k <= 0:
            return min(a, b)
        h = max(k - abs(a - b), 0.0) / k
        return min(a, b) - h * h * k * 0.25

    def sphere_sdf(x, y, z, c, r):
        return float(np.sqrt((x - c[0]) ** 2 + (y - c[1]) ** 2 + (z - c[2]) ** 2) - r)

    def box_sdf(x, y, z, c, s):
        px, py, pz = abs(x - c[0]) - s[0], abs(y - c[1]) - s[1], abs(z - c[2]) - s[2]
        return float(max(px, py, pz))

    def sdf(x, y, z):
        d = 1e9
        for p in prims:
            c = p.get("center", [0, 0, 0])
            s = p.get("size", [50, 50, 50])
            br = float(p.get("blend_radius", 8))
            if p.get("shape") == "box":
                pd = box_sdf(x, y, z, c, [si / 2 for si in s])
            else:
                pd = sphere_sdf(x, y, z, c, max(s) / 2)
            d = smin(d, pd, br) if d < 1e8 else pd
        return d

    return sdf_to_stl(sdf, (-120, 120, -120, 120, -120, 120), res, out_stl)
