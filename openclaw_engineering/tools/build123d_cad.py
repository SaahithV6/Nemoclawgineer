from __future__ import annotations

from pathlib import Path

from openclaw_engineering.models import DeliverableScope
from openclaw_engineering.tools.generative_cad import build_from_geometry_spec
from openclaw_engineering.tools.geometry_catalog import ensure_geometry_spec, infer_part_category
from openclaw_engineering.tools.util import dry_run


def generate_geometry(
    params: dict,
    out_stl: Path,
    user_request: str = "",
    geometry_spec: dict | None = None,
) -> Path:
    """Build manufacturable geometry from geometry_spec + optimizer params."""
    cat = params.get("part_category") or infer_part_category(user_request).value
    spec = ensure_geometry_spec(geometry_spec or {}, user_request, cat)
    spec = {**spec, **{k: v for k, v in params.items() if k not in ("kind",)}}
    discipline = str(params.get("discipline", ""))
    return build_from_geometry_spec(
        spec, params, out_stl, user_request=user_request, discipline=discipline
    )


def generate_rear_wing(params: dict, out_stl: Path) -> Path:
    spec = ensure_geometry_spec(
        {"features": [{"type": "wing", **params}]},
        "",
        "wing",
    )
    return build_from_geometry_spec(spec, params, out_stl)


def generate_downforce_kit(params: dict, out_stl: Path) -> Path:
    spec = ensure_geometry_spec(
        {"features": [{"type": "aero_kit", **params}]},
        "",
        "aero_kit",
    )
    return build_from_geometry_spec(spec, params, out_stl)


def resolve_deliverable_stl(
    deliverable_scope: str,
    addon_stl: Path,
    body_stl: Path | None,
    out_stl: Path,
) -> Path:
    """addon_only → part file only; full_assembly → merge with body when present."""
    out_stl.parent.mkdir(parents=True, exist_ok=True)
    scope = deliverable_scope or DeliverableScope.ADDON_ONLY.value

    if scope == DeliverableScope.BODY_ONLY.value and body_stl and body_stl.exists():
        out_stl.write_bytes(body_stl.read_bytes())
        return out_stl

    if scope == DeliverableScope.FULL_ASSEMBLY.value and body_stl and body_stl.exists():
        return attach_wing_to_body(body_stl, addon_stl, out_stl)

    if dry_run() and not addon_stl.exists():
        out_stl.write_bytes(b"addon deliverable dry-run")
        return out_stl

    out_stl.write_bytes(addon_stl.read_bytes())
    return out_stl


def attach_wing_to_body(body_stl: Path, wing_stl: Path, out_stl: Path) -> Path:
    out_stl.parent.mkdir(parents=True, exist_ok=True)
    if dry_run():
        if body_stl.exists():
            out_stl.write_bytes(body_stl.read_bytes())
        return out_stl
    try:
        import trimesh

        body = trimesh.load(str(body_stl))
        addon = trimesh.load(str(wing_stl))
        combined = trimesh.util.concatenate([body, addon])
        combined.export(str(out_stl))
        return out_stl
    except Exception:
        if body_stl.exists():
            out_stl.write_bytes(body_stl.read_bytes())
        return out_stl
