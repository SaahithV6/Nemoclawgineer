from __future__ import annotations

import math
import struct
from pathlib import Path

from openclaw_engineering.tools.airfoil import naca4_coords
from openclaw_engineering.tools.geometry_catalog import (
    DOWNFORCE_KIT_COMPONENTS,
    GeometryKind,
    clamp_wing_params,
    infer_geometry_kind,
)
from openclaw_engineering.tools.geometry_validate import validate_stl
from openclaw_engineering.tools.util import dry_run, write_json


def _write_simple_stl(tris: list[tuple[tuple[float, float, float], ...]], path: Path) -> None:
    header = b"openclaw-engineering constrained cad" + b"\0" * 56
    buf = bytearray(header[:80])
    buf += struct.pack("<I", len(tris))
    for v1, v2, v3 in tris:
        buf += struct.pack("<12fH", 0, 0, 1, *v1, *v2, *v3, 0)
    path.write_bytes(buf)


def _extrude_airfoil_prism(
    coords: list[tuple[float, float]],
    span_mm: float,
    chord_mm: float,
    y_center: float,
    z_base: float,
) -> list[tuple[tuple[float, float, float], ...]]:
    """Extrude 2D profile along Y (span)."""
    tris: list[tuple[tuple[float, float, float], ...]] = []
    n = len(coords) - 1
    for i in range(n):
        x0, z0 = coords[i]
        x1, z1 = coords[i + 1]
        p00 = (x0 * chord_mm, y_center - span_mm / 2, z0 * chord_mm + z_base)
        p01 = (x1 * chord_mm, y_center - span_mm / 2, z1 * chord_mm + z_base)
        p10 = (x0 * chord_mm, y_center + span_mm / 2, z0 * chord_mm + z_base)
        p11 = (x1 * chord_mm, y_center + span_mm / 2, z1 * chord_mm + z_base)
        tris.append((p00, p01, p10))
        tris.append((p01, p11, p10))
    return tris


def generate_rear_wing(params: dict, out_stl: Path) -> Path:
    """NACA 4-digit extruded wing — not a freeform box."""
    out_stl.parent.mkdir(parents=True, exist_ok=True)
    p = clamp_wing_params(params)
    span = p["span_mm"]
    chord = p["chord_mm"]
    aoa = math.radians(p["angle_of_attack_deg"])
    z_base = float(p.get("mount_offset_mm", 200))
    y_center = float(p.get("y_center_mm", 0))

    if dry_run():
        out_stl.write_bytes(b"naca wing dry-run")
        write_json(out_stl.with_suffix(".json"), p)
        return out_stl

    coords = naca4_coords(p.get("m", 0.02), p.get("p", 0.4), p.get("t", 0.12))
    tris = _extrude_airfoil_prism(coords, span, chord, y_center, z_base)

    # Rotate about Y for AoA
    def rot(pt):
        x, y, z = pt
        cx = math.cos(aoa) * x - math.sin(aoa) * z
        cz = math.sin(aoa) * x + math.cos(aoa) * z
        return (cx, y, cz)

    tris = [tuple(rot(v) for v in t) for t in tris]
    _write_simple_stl(tris, out_stl)
    write_json(out_stl.with_suffix(".json"), p)
    v = validate_stl(out_stl, "rear_wing")
    if not v["valid"]:
        raise ValueError(f"Wing geometry rejected: {v['issues']}")
    return out_stl


def generate_downforce_kit(params: dict, out_stl: Path) -> Path:
    """Conservative kit: splitter, air dam, louvre blocks, diffuser, venturi — boxes in fixed zones."""
    out_stl.parent.mkdir(parents=True, exist_ok=True)
    if dry_run():
        out_stl.write_bytes(b"kit dry-run")
        return out_stl

    tris: list[tuple[tuple[float, float, float], ...]] = []
    wheelbase = float(params.get("wheelbase_mm", 2100))
    track = float(params.get("track_mm", 1400))

    def box(x0, y0, z0, dx, dy, dz):
        corners = [
            (x0, y0, z0),
            (x0 + dx, y0, z0),
            (x0 + dx, y0 + dy, z0),
            (x0, y0 + dy, z0),
            (x0, y0, z0 + dz),
            (x0 + dx, y0, z0 + dz),
            (x0 + dx, y0 + dy, z0 + dz),
            (x0, y0 + dy, z0 + dz),
        ]
        faces = [
            (0, 1, 2),
            (0, 2, 3),
            (4, 6, 5),
            (4, 7, 6),
            (0, 4, 5),
            (0, 5, 1),
            (2, 6, 7),
            (2, 7, 3),
            (0, 3, 7),
            (0, 7, 4),
            (1, 5, 6),
            (1, 6, 2),
        ]
        for f in faces:
            tris.append(tuple(corners[i] for i in f))

    # Front splitter
    box(0, -track / 2, 20, wheelbase * 0.15, track, 8)
    # Air dam
    box(50, -track / 2 + 50, 30, 20, track - 100, 120)
    # Arch louvres (left/right)
    for side in (-1, 1):
        box(400, side * (track / 2 - 80), 400, 300, 40, 60)
    # Rear diffuser
    box(wheelbase * 0.75, -track / 2, 15, wheelbase * 0.2, track, 40)
    # Venturi tunnel (simplified duct over hood)
    box(200, -track / 4, 350, wheelbase * 0.35, track / 2, 80)

    _write_simple_stl(tris, out_stl)
    write_json(
        out_stl.with_suffix(".json"),
        {"kind": GeometryKind.DOWNFORCE_KIT.value, "components": DOWNFORCE_KIT_COMPONENTS},
    )
    return out_stl


def generate_geometry(params: dict, out_stl: Path, user_request: str = "") -> Path:
    kind = params.get("kind") or infer_geometry_kind(user_request).value
    if kind == GeometryKind.DOWNFORCE_KIT.value:
        return generate_downforce_kit(params, out_stl)
    return generate_rear_wing(params, out_stl)


def attach_wing_to_body(body_stl: Path, wing_stl: Path, out_stl: Path) -> Path:
    """Merge body + addon STL; output replaces full car model."""
    out_stl.parent.mkdir(parents=True, exist_ok=True)
    if dry_run():
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
        out_stl.write_bytes(body_stl.read_bytes())
        return out_stl
