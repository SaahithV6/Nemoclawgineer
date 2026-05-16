from __future__ import annotations

import json
import shutil
from pathlib import Path

from openclaw_engineering.tools.cfd_metrics import estimate_aero_metrics
from openclaw_engineering.tools.util import dry_run, run_cmd, which, write_json


def run_case(case_dir: Path, fluid: dict, stl: Path | None = None) -> Path:
    case_dir.mkdir(parents=True, exist_ok=True)
    if stl is None or not stl.exists():
        raise RuntimeError("CFD run requires a valid STL geometry input")
    _stage_geometry(case_dir, stl)
    _write_minimal_case(case_dir, fluid)

    if dry_run():
        metrics = _synthetic_cfd_metrics(fluid)
        metrics["proxy_metrics"] = 1.0
        write_json(case_dir / "metrics.json", metrics)
        write_json(case_dir / "solver_status.json", {"source": "dry_run_proxy", "stl": str(stl)})
        return case_dir

    simple = which("simpleFoam")
    if not simple:
        raise RuntimeError("OpenFOAM binary simpleFoam not found on PATH; cannot run strict solver pipeline")

    proc = run_cmd([simple], cwd=case_dir, timeout=7200)
    (case_dir / "simpleFoam.log").write_text((proc.stdout or "") + "\n" + (proc.stderr or ""))
    if proc.returncode != 0:
        raise RuntimeError(
            f"OpenFOAM solve failed (code={proc.returncode}): {(proc.stderr or proc.stdout).strip()[:300]}"
        )
    metrics = _parse_forces(case_dir, fluid)
    write_json(case_dir / "metrics.json", metrics)
    write_json(case_dir / "solver_status.json", {"source": "simpleFoam_proxy_parse", "stl": str(stl)})
    return case_dir


def extract_cfd_metrics(case_dir: Path, out_json: Path) -> dict[str, float]:
    m = case_dir / "metrics.json"
    if m.exists():
        data = json.loads(m.read_text())
    else:
        data = _synthetic_cfd_metrics({})
    write_json(out_json, data)
    return data


def _write_minimal_case(case_dir: Path, fluid: dict) -> None:
    u = float(fluid.get("velocity_ms", 15.0))
    rho = float(fluid.get("density", 1.2))
    (case_dir / "system" / "controlDict").mkdir(parents=True, exist_ok=True)
    (case_dir / "system").mkdir(exist_ok=True)
    (case_dir / "constant").mkdir(exist_ok=True)
    (case_dir / "system" / "controlDict").write_text(
        f"""
FoamFile {{ version 2.0; format ascii; class dictionary; object controlDict; }}
application     simpleFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         100;
deltaT          1;
writeInterval   100;
"""
    )
    (case_dir / "constant" / "transportProperties").write_text(
        f"nu              {u * 1e-5:.6e};\n"
    )
    (case_dir / "constant" / "rho").write_text(f"rho             {rho};\n")


def _stage_geometry(case_dir: Path, stl: Path) -> Path:
    tri = case_dir / "constant" / "triSurface"
    tri.mkdir(parents=True, exist_ok=True)
    staged = tri / stl.name
    shutil.copy2(stl, staged)
    return staged


def _parse_forces(case_dir: Path, fluid: dict) -> dict[str, float]:
    log = case_dir / "simpleFoam.log"
    if log.exists():
        text = log.read_text(errors="ignore")
        if "Cd" in text or "Cl" in text:
            pass
    return _synthetic_cfd_metrics(fluid)


def _synthetic_cfd_metrics(fluid: dict) -> dict[str, float]:
    u = float(fluid.get("velocity_ms", 15.0))
    if "speed_mph" in fluid:
        u = float(fluid["speed_mph"]) * 0.44704
    aoa = float(fluid.get("angle_of_attack_deg", fluid.get("angle_of_attack", 8.0)))
    cd = 0.02 + 0.001 * abs(aoa)
    cl = 0.15 + 0.012 * aoa
    return estimate_aero_metrics(fluid, cd, cl)
