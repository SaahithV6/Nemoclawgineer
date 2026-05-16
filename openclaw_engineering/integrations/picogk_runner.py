from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from openclaw_engineering.config import REPO_ROOT, get_settings
from openclaw_engineering.tools.util import dry_run, which, write_json

DRIVER_PROJECT = REPO_ROOT / "picogk_driver" / "OpenClawEngineering.PicoGK.csproj"


class PicoGKUnavailable(RuntimeError):
    pass


def picogk_status() -> dict[str, Any]:
    """Probe optional PicoGK backends for doctor / MCP."""
    dotnet = which("dotnet")
    driver = DRIVER_PROJECT.exists()
    runtime = os.environ.get("PICOGK_RUNTIME_PATH", "")
    pycogk = False
    try:
        import picogk  # noqa: F401

        pycogk = True
    except ImportError:
        pass
    enabled = get_settings().openclaw_engineering_picogk_enabled
    return {
        "enabled_setting": enabled,
        "dotnet": bool(dotnet),
        "driver_project": driver,
        "pycogk_import": pycogk,
        "picogk_runtime_path": runtime or None,
        "ready": enabled and bool(dotnet) and driver,
    }


def params_to_job(params: dict[str, Any], input_stl: str | None = None) -> dict[str, Any]:
    """Map geometry_spec.params → PicoGK job.json operations."""
    voxel = float(params.get("voxel_size_mm", 0.5))
    ops: list[dict[str, Any]] = list(params.get("operations") or [])

    if not ops:
        # Default: lattice from spheres + beams
        if input_stl and Path(input_stl).exists():
            ops.append({"type": "stl_import", "path": str(input_stl), "boolean": "add"})
        for sp in params.get("spheres") or []:
            ops.append(
                {
                    "type": "sphere",
                    "center": sp.get("center", [0, 0, 0]),
                    "radius": sp.get("radius_mm", 10),
                    "boolean": sp.get("boolean", "add"),
                }
            )
        for bm in params.get("beams") or []:
            ops.append(
                {
                    "type": "beam",
                    "a": bm.get("a", [0, 0, 0]),
                    "b": bm.get("b", [10, 0, 0]),
                    "radius": bm.get("radius_mm", 3),
                    "boolean": bm.get("boolean", "add"),
                }
            )
        if not ops:
            r = float(params.get("radius_mm", 40))
            ops.append({"type": "sphere", "center": [0, 0, 0], "radius": r, "boolean": "add"})

    return {"voxel_size_mm": voxel, "operations": ops}


def run_picogk_job(job: dict[str, Any], out_stl: Path, work_dir: Path | None = None) -> Path:
    """Execute PicoGK driver (dotnet). Uses xvfb-run on Linux when available."""
    if dry_run():
        out_stl.parent.mkdir(parents=True, exist_ok=True)
        out_stl.write_bytes(b"picogk dry-run stl")
        write_json(out_stl.with_suffix(".json"), job)
        return out_stl

    st = picogk_status()
    if not st["ready"]:
        raise PicoGKUnavailable(
            "PicoGK not ready: set OPENCLAW_ENGINEERING_PICOGK_ENABLED=1, install .NET 9 SDK, "
            "and ensure picogk_driver builds. See docs/PICOGK.md"
        )

    work = work_dir or out_stl.parent
    work.mkdir(parents=True, exist_ok=True)
    job_path = work / "picogk_job.json"
    job_path.write_text(json.dumps(job, indent=2))

    dotnet = which("dotnet")
    assert dotnet
    cmd = [
        dotnet,
        "run",
        "--project",
        str(DRIVER_PROJECT),
        "-c",
        "Release",
        "--",
        str(job_path),
        str(out_stl),
    ]
    env = os.environ.copy()
    if get_settings().openclaw_engineering_picogk_runtime_path:
        env["PICOGK_RUNTIME_PATH"] = get_settings().openclaw_engineering_picogk_runtime_path

    wrapper = which("xvfb-run")
    if wrapper and os.name != "nt":
        cmd = [wrapper, "-a"] + cmd

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=env, cwd=str(REPO_ROOT))
    if proc.returncode != 0:
        raise RuntimeError(
            f"PicoGK driver failed ({proc.returncode}):\n{proc.stderr[-2000:]}\n{proc.stdout[-500:]}"
        )
    if not out_stl.exists():
        raise RuntimeError("PicoGK did not produce output STL")
    write_json(out_stl.with_suffix(".json"), {"job": job, "log": proc.stdout[-500:]})
    return out_stl


def try_pycogk_job(job: dict[str, Any], out_stl: Path) -> Path | None:
    """Optional pycogk path (win-x64 / osx-arm64 bundles). Returns None if unavailable."""
    try:
        from picogk import Lattice, Mesh, VedoViewer, Voxels, go
    except ImportError:
        return None

    out_stl.parent.mkdir(parents=True, exist_ok=True)
    acc = None

    def task() -> None:
        nonlocal acc
        for op in job.get("operations", []):
            piece = None
            if op["type"] == "sphere":
                c = op.get("center", [0, 0, 0])
                with Lattice() as lat:
                    lat.AddSphere(tuple(c), float(op.get("radius", 10)))
                    with Voxels.from_lattice(lat) as vox:
                        piece = vox
            if piece is None:
                continue
            if acc is None:
                acc = piece
            else:
                acc = acc + piece
        if acc is None:
            return
        with Mesh.from_voxels(acc) as msh:
            msh.save(str(out_stl))

    go(job.get("voxel_size_mm", 0.5), task, end_on_task_completion=True)
    return out_stl if out_stl.exists() else None


def build_stl(params: dict[str, Any], out_stl: Path, input_stl: str | None = None) -> Path:
    job = params_to_job(params, input_stl)
    try:
        alt = try_pycogk_job(job, out_stl)
        if alt:
            return alt
    except Exception:
        pass
    return run_picogk_job(job, out_stl)
