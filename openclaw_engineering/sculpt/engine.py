from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from openclaw_engineering.sculpt.registry import SCULPT_METHODS, infer_sculpt_method
from openclaw_engineering.tools.geometry_validate import validate_stl
from openclaw_engineering.tools.util import dry_run, write_json


def list_sculpt_methods() -> list[dict[str, Any]]:
    return [
        {
            "id": m.id,
            "name": m.name,
            "description": m.description,
            "physics": m.physics,
        }
        for m in SCULPT_METHODS.values()
    ]


def sculpt_method_schema(method_id: str) -> dict[str, Any]:
    m = SCULPT_METHODS.get(method_id)
    if not m:
        return {"error": f"unknown method {method_id}", "available": list(SCULPT_METHODS)}
    return {"id": m.id, "name": m.name, "description": m.description, "param_schema": m.param_schema}


def build_sculpt(
    geometry_spec: dict[str, Any],
    params: dict[str, Any],
    out_stl: Path,
    *,
    user_request: str = "",
    discipline: str = "",
    input_stl: str | None = None,
    fluid: dict[str, Any] | None = None,
) -> Path:
    """
    Dynamic sculpt entry: geometry_spec.sculpt_method + geometry_spec.params.
    Legacy geometry_spec.features[] still supported via bracket_parametric / wing_loft mapping.
    """
    out_stl.parent.mkdir(parents=True, exist_ok=True)
    method_id = geometry_spec.get("sculpt_method") or geometry_spec.get("method")
    if not method_id:
        method_id = _method_from_legacy_features(geometry_spec) or infer_sculpt_method(
            user_request, discipline
        )

    merged = {**geometry_spec.get("params", {}), **params}
    body_stl_path = input_stl or geometry_spec.get("input_stl")
    if body_stl_path:
        from openclaw_engineering.feasibility import apply_feasibility_to_spec

        geometry_spec, _fb = apply_feasibility_to_spec(
            {**geometry_spec, "params": merged},
            body_stl=Path(body_stl_path),
            fluid=fluid,
        )
        merged = geometry_spec.get("params", merged)

    if dry_run():
        out_stl.write_bytes(f"sculpt:{method_id}".encode())
        write_json(out_stl.with_suffix(".json"), {"sculpt_method": method_id, "params": merged})
        return out_stl

    method = SCULPT_METHODS.get(method_id)
    if not method:
        raise ValueError(f"Unknown sculpt_method '{method_id}'. Call list_sculpt_methods.")

    mod = importlib.import_module(method.builder)
    mod.build(merged, out_stl, input_stl=input_stl or geometry_spec.get("input_stl"))

    body_path = Path(body_stl_path) if body_stl_path else None
    if body_path and body_path.exists() and geometry_spec.get("mount_envelope"):
        from openclaw_engineering.feasibility import verify_addon_fits_body

        fit = verify_addon_fits_body(out_stl, body_path, geometry_spec["mount_envelope"])
        if not fit["fits"]:
            raise ValueError(f"Geometry does not fit vehicle mount envelope: {fit['issues']}")

    meta = {"sculpt_method": method_id, "params": merged}
    write_json(out_stl.with_suffix(".json"), meta)
    v = validate_stl(out_stl, method_id)
    if not v["valid"]:
        raise ValueError(f"Sculpt output failed checks: {v['issues']}")
    return out_stl


def _method_from_legacy_features(geometry_spec: dict[str, Any]) -> str | None:
    feats = geometry_spec.get("features") or []
    if not feats:
        return None
    t = feats[0].get("type", "")
    if t == "wing":
        return "wing_loft"
    if t in ("bracket", "gusset"):
        return "bracket_parametric"
    if t == "aero_kit":
        return "sdf_compose"
    return None
