from __future__ import annotations

"""Part labels and defaults for generative geometry — not hard routing."""

from enum import Enum
from pathlib import Path
from typing import Any

from openclaw_engineering.models import PartCategory
from openclaw_engineering.tools.geometry_spec import default_geometry_spec, infer_features_from_request


class GeometryKind(str, Enum):
    """Legacy enum — prefer PartCategory."""
    REAR_WING = "rear_wing"
    DOWNFORCE_KIT = "downforce_kit"


def infer_part_category(user_text: str) -> PartCategory:
    t = user_text.lower()
    if any(k in t for k in ("bracket", "mount", "gusset", "clevis")):
        return PartCategory.BRACKET
    if any(
        k in t
        for k in ("downforce kit", "splitter", "diffuser", "louvre", "louver", "venturi", "aero kit")
    ):
        return PartCategory.AERO_KIT
    if any(k in t for k in ("wing", "airfoil", "spoiler", "rear wing")):
        return PartCategory.WING
    if any(k in t for k in ("frame", "chassis", "beam", "truss")):
        return PartCategory.STRUCTURAL
    return PartCategory.CUSTOM


def infer_geometry_kind(user_text: str) -> GeometryKind:
    cat = infer_part_category(user_text)
    if cat == PartCategory.AERO_KIT:
        return GeometryKind.DOWNFORCE_KIT
    return GeometryKind.REAR_WING


def ensure_geometry_spec(spec_dict: dict[str, Any], user_request: str, part_category: str) -> dict[str, Any]:
    gs = dict(spec_dict) if spec_dict else default_geometry_spec(part_category)
    if not gs.get("features"):
        gs["features"] = infer_features_from_request(user_request, part_category)
    gs["part_category"] = part_category
    return gs


def design_params_from_geometry_spec(geometry_spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Numeric fields the optimizer may tune per pass."""
    params: list[dict[str, Any]] = []
    sculpt_params = geometry_spec.get("params") or {}
    for key, val in sculpt_params.items():
        if isinstance(val, (int, float)):
            lo, hi = float(val) * 0.7, float(val) * 1.3
            if key.endswith("_deg"):
                lo, hi = float(val) - 10, float(val) + 10
            params.append({"name": key, "min": lo, "max": hi, "initial": float(val)})
    if params:
        return params
    for feat in geometry_spec.get("features", []):
        for key, val in feat.items():
            if isinstance(val, (int, float)) and key.endswith(("_mm", "_deg")):
                lo = float(val) * 0.6
                hi = float(val) * 1.4
                if key.endswith("_deg"):
                    lo, hi = max(-5, float(val) - 8), min(25, float(val) + 8)
                params.append({"name": key, "min": lo, "max": hi, "initial": float(val)})
    return params


def grabcad_reference_hint(query: str) -> str:
    q = query.replace(" ", "+")
    return f"https://grabcad.com/library?query={q}"


def load_reference_stl(path: str | None) -> Path | None:
    if not path:
        return None
    p = Path(path)
    return p if p.exists() else None
