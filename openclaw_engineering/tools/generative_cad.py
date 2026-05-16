from __future__ import annotations

from pathlib import Path
from typing import Any

from openclaw_engineering.tools.geometry_spec import merge_params_into_spec


def build_from_geometry_spec(
    geometry_spec: dict[str, Any],
    params: dict[str, Any],
    out_stl: Path,
    *,
    user_request: str = "",
    discipline: str = "",
    input_stl: str | None = None,
) -> Path:
    """Delegate all geometry to the dynamic sculpt engine."""
    from openclaw_engineering.sculpt.engine import _method_from_legacy_features, build_sculpt
    from openclaw_engineering.sculpt.registry import infer_sculpt_method

    spec = dict(geometry_spec)
    if not spec.get("sculpt_method"):
        legacy = _method_from_legacy_features(spec)
        spec["sculpt_method"] = legacy or infer_sculpt_method(user_request, discipline)
        if spec.get("features") and not spec.get("params"):
            spec["params"] = {**spec["features"][0]}
            spec["params"].pop("type", None)

    merged = merge_spec_params(spec, params)
    return build_sculpt(
        merged,
        params,
        out_stl,
        user_request=user_request,
        discipline=discipline,
        input_stl=input_stl,
        fluid=geometry_spec.get("_fluid") or geometry_spec.get("fluid"),
    )


def merge_spec_params(geometry_spec: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    if not params:
        return dict(geometry_spec)
    inner = dict(geometry_spec.get("params") or {})
    for k, v in params.items():
        if isinstance(v, (int, float)):
            inner[k] = v
    out = dict(geometry_spec)
    out["params"] = inner
    return merge_params_into_spec(out, params)
