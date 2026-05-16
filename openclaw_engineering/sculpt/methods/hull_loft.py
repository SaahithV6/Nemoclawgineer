from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from openclaw_engineering.sculpt.mesh_common import loft_sections, write_stl


def build(params: dict[str, Any], out_stl: Path, **kwargs: Any) -> Path:
    length = float(params.get("length_mm", 2000))
    beam = float(params.get("beam_mm", 600))
    draft = float(params.get("draft_mm", 280))
    n = int(params.get("station_count", 16))
    bow = float(params.get("bow_fullness", 0.6))
    stern = float(params.get("stern_fullness", 0.5))
    rocker = float(params.get("rocker_mm", 40))

    sections: list[list[tuple[float, float, float]]] = []
    for i in range(n):
        x = length * i / max(n - 1, 1)
        eta = i / max(n - 1, 1)
        # Fullness envelope along length
        env = np.sin(np.pi * eta) ** 0.85
        if eta < 0.25:
            env *= bow + (1 - bow) * (eta / 0.25)
        if eta > 0.75:
            env *= stern + (1 - stern) * ((1 - eta) / 0.25)
        half_beam = beam * 0.5 * env
        z_keel = -draft * env + rocker * (eta - 0.5) ** 2
        ring = []
        for t in range(24):
            ang = 2 * np.pi * t / 24
            y = half_beam * np.cos(ang)
            z = z_keel + half_beam * 0.35 * np.sin(ang)
            ring.append((float(x), float(y), float(z)))
        sections.append(ring)

    write_stl(loft_sections(sections), out_stl)
    return out_stl
