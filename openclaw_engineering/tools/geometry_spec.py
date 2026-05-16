from __future__ import annotations

"""
Structured geometry description from Discord Q&A → manufacturable mesh.

The agent fills `geometry_spec` after clarification; the executor builds meshes
from `features[]` (brackets, wings, gussets, organic blends, holes, aero volumes).
"""

from typing import Any


def default_geometry_spec(part_category: str = "custom") -> dict[str, Any]:
    return {
        "part_category": part_category,
        "features": [],
        "tolerance_mm": 0.5,
        "material": "",
        "machining_notes": "",
        "units": "mm",
    }


def merge_params_into_spec(spec_dict: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """Apply optimizer / agent numeric tweaks onto sculpt params or legacy features."""
    out = dict(spec_dict)
    inner = dict(out.get("params") or {})
    for k, v in params.items():
        if isinstance(v, (int, float)) or k.endswith(("_mm", "_deg", "_bias")):
            inner[k] = v
    if inner:
        out["params"] = inner
        return out
    features = [dict(f) for f in out.get("features", [])]
    if not features:
        return out
    f0 = features[0]
    for k, v in params.items():
        if k in f0 or k.endswith("_mm") or k.endswith("_deg"):
            f0[k] = v
    features[0] = f0
    out["features"] = features
    return out


def infer_features_from_request(user_request: str, part_category: str) -> list[dict[str, Any]]:
    """Seed features when the agent has not supplied geometry_spec yet."""
    t = user_request.lower()
    if part_category == "wing" or any(w in t for w in ("wing", "airfoil", "spoiler")):
        return [
            {
                "type": "wing",
                "profile": "naca2412",
                "span_mm": 1200,
                "chord_mm": 280,
                "angle_of_attack_deg": 8,
                "thickness_mm": 18,
            }
        ]
    if part_category == "bracket" or "bracket" in t:
        return [
            {
                "type": "bracket",
                "style": "L",
                "leg_a_mm": 80,
                "leg_b_mm": 60,
                "thickness_mm": 8,
                "bend_angle_deg": 90,
                "fillet_radius_mm": 6,
                "join_pattern": "gusseted",
            }
        ]
    if part_category == "aero_kit" or any(
        k in t for k in ("splitter", "diffuser", "louvre", "venturi", "aero kit")
    ):
        return [{"type": "aero_kit", "wheelbase_mm": 2100, "track_mm": 1400}]
    return [{"type": "custom_block", "size_mm": [100, 80, 40]}]
