from __future__ import annotations

from pathlib import Path
from typing import Any

from openclaw_engineering.config import get_settings
from openclaw_engineering.integrations.picogk_runner import PicoGKUnavailable, build_stl, picogk_status
from openclaw_engineering.sculpt.methods import sdf_compose


def build(params: dict[str, Any], out_stl: Path, **kwargs: Any) -> Path:
    """
    LEAP71 PicoGK field/lattice pipeline (optional).
    Falls back to internal SDF sculpt if PicoGK is not installed/enabled.
    """
    settings = get_settings()
    if not settings.openclaw_engineering_picogk_enabled:
        return _fallback(params, out_stl, reason="OPENCLAW_ENGINEERING_PICOGK_ENABLED=0")

    st = picogk_status()
    if not st["ready"]:
        return _fallback(params, out_stl, reason="PicoGK not installed — see docs/PICOGK.md")

    try:
        return build_stl(params, out_stl, input_stl=kwargs.get("input_stl"))
    except PicoGKUnavailable as exc:
        return _fallback(params, out_stl, reason=str(exc))


def _fallback(params: dict[str, Any], out_stl: Path, reason: str) -> Path:
    meta = dict(params)
    meta["_picogk_fallback"] = reason
    prims = params.get("primitives")
    if not prims:
        prims = []
        for sp in params.get("spheres") or [{"center": [0, 0, 0], "radius_mm": 40}]:
            c = sp.get("center", [0, 0, 0])
            r = float(sp.get("radius_mm", 10))
            prims.append(
                {
                    "shape": "sphere",
                    "center": c,
                    "size": [r * 2, r * 2, r * 2],
                    "blend_radius": float(params.get("blend_radius_mm", 8)),
                }
            )
    return sdf_compose.build({"resolution": params.get("resolution", 56), "primitives": prims}, out_stl)
