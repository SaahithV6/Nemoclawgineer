from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from openclaw_engineering.sculpt.mesh_common import revolve_profile, write_stl


def build(params: dict[str, Any], out_stl: Path, **kwargs: Any) -> Path:
    length = float(params.get("length_mm", 400))
    r_throat = float(params.get("throat_radius_mm", 25))
    r_exit = float(params.get("exit_radius_mm", 80))
    n = int(params.get("contour_points", 24))
    div_deg = math.radians(float(params.get("divergence_deg", 15)))
    wall = float(params.get("wall_thickness_mm", 4))

    profile: list[tuple[float, float]] = []
    for i in range(n):
        t = i / max(n - 1, 1)
        y = t * length
        # Smooth area growth (simplified Rao / conical blend)
        r_inner = r_throat + (r_exit - r_throat) * (t ** 0.7)
        r_inner += math.tan(div_deg) * y * 0.15
        profile.append((r_inner + wall, y))
    # Close inner wall back toward throat
    for i in range(n - 1, -1, -1):
        t = i / max(n - 1, 1)
        y = t * length
        r_inner = r_throat + (r_exit - r_throat) * (t ** 0.7)
        profile.append((max(r_throat * 0.9, r_inner), y))

    write_stl(revolve_profile(profile, segments=40), out_stl)
    return out_stl
