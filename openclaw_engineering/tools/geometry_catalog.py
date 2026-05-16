from __future__ import annotations

"""Constrained geometry presets — avoids freeform 'crazy' meshes."""

from enum import Enum
from pathlib import Path
from typing import Any


class GeometryKind(str, Enum):
    REAR_WING = "rear_wing"
    DOWNFORCE_KIT = "downforce_kit"


# NACA 2412 — common rear wing profile (cambered, realistic)
WING_PRESET = {
    "kind": GeometryKind.REAR_WING,
    "naca": "2412",
    "m": 0.02,
    "p": 0.4,
    "t": 0.12,
    "max_span_mm": 1600,
    "max_chord_mm": 450,
    "min_chord_mm": 180,
}

DOWNFORCE_KIT_COMPONENTS = [
    "front_splitter",
    "front_air_dam",
    "front_arch_louvres",
    "underbody_diffuser",
    "front_venturi_duct",
]


def infer_geometry_kind(user_text: str) -> GeometryKind:
    t = user_text.lower()
    if any(
        k in t
        for k in (
            "downforce kit",
            "splitter",
            "diffuser",
            "louvre",
            "louver",
            "air dam",
            "venturi",
            "aero kit",
        )
    ):
        return GeometryKind.DOWNFORCE_KIT
    return GeometryKind.REAR_WING


def clamp_wing_params(params: dict[str, Any]) -> dict[str, Any]:
    p = dict(params)
    p["span_mm"] = max(600, min(WING_PRESET["max_span_mm"], float(p.get("span_mm", 1200))))
    p["chord_mm"] = max(
        WING_PRESET["min_chord_mm"],
        min(WING_PRESET["max_chord_mm"], float(p.get("chord_mm", 280))),
    )
    p["angle_of_attack_deg"] = max(-2, min(16, float(p.get("angle_of_attack_deg", 8))))
    p["thickness_mm"] = max(8, min(35, float(p.get("thickness_mm", 18))))
    p["kind"] = GeometryKind.REAR_WING.value
    p["naca"] = WING_PRESET["naca"]
    return p


def grabcad_reference_hint(query: str) -> str:
    """No GrabCAD API key in hackathon build — return search URL for manual reference."""
    q = query.replace(" ", "+")
    return f"https://grabcad.com/library?query={q}"


def load_reference_stl(path: str | None) -> Path | None:
    if not path:
        return None
    p = Path(path)
    return p if p.exists() else None
