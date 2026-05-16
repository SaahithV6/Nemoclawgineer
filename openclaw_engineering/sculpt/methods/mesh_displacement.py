from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


def build(params: dict[str, Any], out_stl: Path, **kwargs: Any) -> Path:
    inp = params.get("input_stl") or kwargs.get("input_stl")
    if not inp or not Path(inp).exists():
        from openclaw_engineering.sculpt.methods import sdf_compose

        return sdf_compose.build({"resolution": 32}, out_stl)

    import trimesh

    amp = float(params.get("amplitude_mm", 5))
    freq = float(params.get("frequency", 1.0))
    direction = np.array(params.get("direction", [0, 0, 1]), dtype=float)
    direction = direction / (np.linalg.norm(direction) + 1e-9)

    mesh = trimesh.load(str(inp))
    verts = np.array(mesh.vertices)
    disp = amp * np.sin(freq * verts[:, 0] * 0.01)[:, None] * direction
    mesh.vertices = verts + disp
    mesh.export(str(out_stl))
    return out_stl
