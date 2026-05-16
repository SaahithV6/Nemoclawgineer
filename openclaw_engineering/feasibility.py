from __future__ import annotations

"""
Reality checks before/after sculpt — mount fit, envelope, downforce vs size.

Optimization must NOT blindly scale span/chord until the wing ignores the car body.
"""

from pathlib import Path
from typing import Any

import numpy as np


def stl_bounds(stl_path: Path | None) -> dict[str, float] | None:
    if not stl_path or not stl_path.exists():
        return None
    try:
        import trimesh

        m = trimesh.load(str(stl_path))
        b = m.bounding_box.bounds
        mn, mx = b[0], b[1]
        return {
            "xmin": float(mn[0]),
            "ymin": float(mn[1]),
            "zmin": float(mn[2]),
            "xmax": float(mx[0]),
            "ymax": float(mx[1]),
            "zmax": float(mx[2]),
            "xspan": float(mx[0] - mn[0]),
            "yspan": float(mx[1] - mn[1]),
            "zspan": float(mx[2] - mn[2]),
        }
    except Exception:
        return None


def mount_envelope_from_body(body_bounds: dict[str, float]) -> dict[str, float]:
    """Rear deck / trunk mount zone heuristics for a typical car body STL (mm)."""
    x_rear = body_bounds["xmax"] - body_bounds["xspan"] * 0.08
    return {
        "x_min": x_rear - body_bounds["xspan"] * 0.35,
        "x_max": body_bounds["xmax"] + body_bounds["xspan"] * 0.05,
        "y_min": body_bounds["ymin"] + body_bounds["yspan"] * 0.12,
        "y_max": body_bounds["ymax"] - body_bounds["yspan"] * 0.12,
        "z_min": body_bounds["zmin"] + body_bounds["zspan"] * 0.45,
        "z_max": body_bounds["zmax"] + body_bounds["zspan"] * 0.35,
        "max_span_mm": body_bounds["yspan"] * 0.92,
        "max_chord_mm": body_bounds["xspan"] * 0.28,
    }


def clamp_wing_params_to_envelope(
    params: dict[str, Any],
    envelope: dict[str, float],
    body_bounds: dict[str, float] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Clamp sculpt params so the wing stays on the car — never only scale for downforce."""
    p = dict(params)
    notes: list[str] = []

    max_span = float(envelope.get("max_span_mm", 1600))
    max_chord = float(envelope.get("max_chord_mm", 450))
    max_chord = min(max_chord, 500)

    span = float(p.get("span_mm", p.get("span_mm", 1200)))
    if span > max_span:
        notes.append(f"span clamped {span:.0f} → {max_span:.0f} mm (body width)")
        p["span_mm"] = max_span

    for key in ("chord_root_mm", "chord_mm"):
        if key in p:
            c = float(p[key])
            if c > max_chord:
                notes.append(f"{key} clamped {c:.0f} → {max_chord:.0f} mm (mount zone)")
                p[key] = max_chord

    if "chord_tip_mm" in p:
        tip = min(float(p["chord_tip_mm"]), float(p.get("chord_root_mm", max_chord)) * 0.85)
        p["chord_tip_mm"] = tip

    # Mount offset: place root near rear deck
    if body_bounds:
        z_base = body_bounds["zmax"] - body_bounds["zspan"] * 0.05
        p["mount_offset_z_mm"] = z_base
        p.setdefault("y_center_mm", (body_bounds["ymin"] + body_bounds["ymax"]) / 2)

    # Downforce ambition: prefer aero tuning over giant planform
    target_lbs = float(p.get("_target_downforce_lbs", 0))
    if target_lbs > 400 and span >= max_span * 0.95:
        notes.append(
            "High downforce target: holding planform at body limit; use camber_bias/AoA in optimization, "
            "not larger span."
        )
        p["camber_bias"] = min(1.0, float(p.get("camber_bias", 0)) + 0.15)
        p.setdefault("angle_of_attack_deg", min(14, float(p.get("angle_of_attack_deg", 8)) + 2))

    return p, notes


def verify_addon_fits_body(
    addon_stl: Path,
    body_stl: Path,
    envelope: dict[str, float],
) -> dict[str, Any]:
    """Post-build check: addon bbox vs mount envelope."""
    ab = stl_bounds(addon_stl)
    if not ab:
        return {"fits": True, "issues": []}
    issues: list[str] = []
    if ab["yspan"] > envelope.get("max_span_mm", 1e9) * 1.02:
        issues.append(f"addon span {ab['yspan']:.0f} mm exceeds body mount envelope")
    if ab["xspan"] > envelope.get("max_chord_mm", 1e9) * 2.5:
        issues.append(f"addon chord/extent {ab['xspan']:.0f} mm unrealistic for mount zone")
    if ab["zmin"] < envelope.get("z_min", -1e9) - 50:
        issues.append("addon extends below allowable mount height")
    return {"fits": len(issues) == 0, "issues": issues, "addon_bounds": ab}


def apply_feasibility_to_spec(
    geometry_spec: dict[str, Any],
    *,
    body_stl: Path | None = None,
    fluid: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Returns (updated geometry_spec, feasibility_meta) stored on job for report.
    """
    meta: dict[str, Any] = {"checks": [], "envelope": None}
    body_bounds = stl_bounds(body_stl)
    if not body_bounds:
        return geometry_spec, meta

    envelope = mount_envelope_from_body(body_bounds)
    meta["envelope"] = envelope
    meta["body_bounds"] = body_bounds

    params = dict(geometry_spec.get("params") or {})
    if fluid and fluid.get("target_downforce_lbs"):
        params["_target_downforce_lbs"] = float(fluid["target_downforce_lbs"])

    method = geometry_spec.get("sculpt_method", "")
    if method == "wing_loft" or geometry_spec.get("features", [{}])[0].get("type") == "wing":
        params, notes = clamp_wing_params_to_envelope(params, envelope, body_bounds)
        meta["checks"].extend(notes)

    geometry_spec = {**geometry_spec, "params": params}
    geometry_spec["mount_envelope"] = envelope
    return geometry_spec, meta
