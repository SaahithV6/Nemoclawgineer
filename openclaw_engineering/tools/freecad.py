from __future__ import annotations

import json
import math
import struct
from pathlib import Path

from openclaw_engineering.tools.util import dry_run, run_cmd, which, write_json


def _read_stl_triangles(stl_path: Path) -> list[tuple[tuple[float, float, float], ...]]:
    data = stl_path.read_bytes()
    if data[:5] == b"solid":
        return _read_ascii_stl(stl_path)
    return _read_binary_stl(data)


def _read_binary_stl(data: bytes) -> list[tuple[tuple[float, float, float], ...]]:
    if len(data) < 84:
        return []
    n = struct.unpack_from("<I", data, 80)[0]
    tris: list[tuple[tuple[float, float, float], ...]] = []
    off = 84
    for _ in range(n):
        if off + 50 > len(data):
            break
        vals = struct.unpack_from("<12fH", data, off)
        v1 = (vals[3], vals[4], vals[5])
        v2 = (vals[6], vals[7], vals[8])
        v3 = (vals[9], vals[10], vals[11])
        tris.append((v1, v2, v3))
        off += 50
    return tris


def _read_ascii_stl(path: Path) -> list[tuple[tuple[float, float, float], ...]]:
    tris: list[tuple[tuple[float, float, float], ...]] = []
    verts: list[tuple[float, float, float]] = []
    for line in path.read_text(errors="ignore").splitlines():
        parts = line.strip().split()
        if len(parts) == 4 and parts[0] == "vertex":
            verts.append((float(parts[1]), float(parts[2]), float(parts[3])))
            if len(verts) == 3:
                tris.append((verts[0], verts[1], verts[2]))
                verts = []
    return tris


def _write_binary_stl(path: Path, tris: list[tuple[tuple[float, float, float], ...]]) -> None:
    header = b"openclaw-engineering deform" + b"\0" * 65
    buf = bytearray(header[:80])
    buf += struct.pack("<I", len(tris))
    for v1, v2, v3 in tris:
        buf += struct.pack("<12fH", 0, 0, 0, *v1, *v2, *v3, 0)
    path.write_bytes(buf)


def deform_stl(stl_in: Path, params: dict[str, float], out_stl: Path) -> Path:
    """Parametric STL deform: thickness_scale uniform scale on Z-normal thickness proxy."""
    out_stl.parent.mkdir(parents=True, exist_ok=True)
    scale = float(params.get("thickness_scale", params.get("thickness_mm", 1.0)))
    if scale > 10:
        scale = scale / 10.0
    scale = max(0.5, min(2.0, scale if scale else 1.0))

    if dry_run():
        out_stl.write_bytes(stl_in.read_bytes())
        write_json(out_stl.with_suffix(".deform.json"), {"params": params, "scale": scale})
        return out_stl

    import os

    appimage = os.environ.get("OPENCLAW_ENGINEERING_FREECAD_APPIMAGE", "")
    freecad = which("freecadcmd") or which("FreeCADCmd")
    if appimage and Path(appimage).exists():
        freecad = appimage
    if freecad:
        macro = out_stl.parent / "deform_macro.py"
        macro.write_text(
            f"""
import Mesh
m = Mesh.Mesh()
m.read("{stl_in}")
m.scale({scale}, {scale}, {scale})
m.write("{out_stl}")
"""
        )
        proc = run_cmd([freecad, str(macro)], timeout=600)
        if proc.returncode == 0 and out_stl.exists():
            return out_stl

    tris = _read_stl_triangles(stl_in)
    if not tris:
        out_stl.write_bytes(stl_in.read_bytes())
        return out_stl

    cx = sum(sum(v[0] for v in t) for t in tris) / (3 * len(tris))
    cy = sum(sum(v[1] for v in t) for t in tris) / (3 * len(tris))
    cz = sum(sum(v[2] for v in t) for t in tris) / (3 * len(tris))

    def deform_point(p: tuple[float, float, float]) -> tuple[float, float, float]:
        dx, dy, dz = p[0] - cx, p[1] - cy, p[2] - cz
        r = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        factor = 1.0 + (scale - 1.0) * (abs(dz) / (abs(dz) + r))
        return (cx + dx * factor, cy + dy * factor, cz + dz * factor)

    new_tris = [tuple(deform_point(v) for v in t) for t in tris]
    _write_binary_stl(out_stl, new_tris)
    write_json(out_stl.with_suffix(".deform.json"), {"params": params, "scale": scale})
    return out_stl
