from __future__ import annotations

import json
from pathlib import Path

from openclaw_engineering.tools.calculix import run as ccx_run
from openclaw_engineering.tools.fea import extract_metrics
from openclaw_engineering.tools.gmsh import mesh_stl
from openclaw_engineering.tools.util import write_json


def stress_test_wing(
    wing_stl: Path,
    loads: dict,
    work_dir: Path,
    reinforce: bool = False,
) -> dict:
    """
    FEA on wing STL; identify max stress and suggest rib thickness if over limit.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    inp = work_dir / "wing.inp"
    mesh_stl(wing_stl, float(loads.get("mesh_size", 3.0)), inp)
    results = ccx_run(inp, loads, work_dir / "ccx")
    metrics_path = work_dir / "metrics.json"
    metrics = extract_metrics(results, metrics_path)

    yield_mpa = float(loads.get("yield_strength_mpa", 275))  # aluminum
    max_stress = metrics.get("max_stress_mpa", 0)
    failure_zones = []
    if max_stress > yield_mpa * 0.85:
        failure_zones.append(
            {
                "zone": "main_spar_region",
                "max_stress_mpa": max_stress,
                "recommendation": "Increase rib thickness 15-25% or add endplate gusset",
            }
        )
    if max_stress > yield_mpa:
        failure_zones.append(
            {
                "zone": "potential_yield",
                "action": "add_spar_cap" if reinforce else "flag_for_redesign",
            }
        )

    out = {
        "metrics": metrics,
        "yield_mpa": yield_mpa,
        "failure_zones": failure_zones,
        "feasible": max_stress < yield_mpa,
        "reinforce_applied": reinforce,
    }
    write_json(work_dir / "wing_fea.json", out)
    return out
