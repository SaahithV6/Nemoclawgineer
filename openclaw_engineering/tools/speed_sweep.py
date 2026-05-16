from __future__ import annotations

import json
from pathlib import Path

from openclaw_engineering.tools.cfd_metrics import estimate_aero_metrics, mph_to_ms
from openclaw_engineering.tools.openfoam import run_case
from openclaw_engineering.tools.util import dry_run, write_json


# Stock 914-6 ~130 mph; wing adds drag — report through this range
DEFAULT_SWEEP_MPH = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130]


def run_speed_sweep(
    combined_stl: Path,
    fluid: dict,
    out_dir: Path,
    speeds_mph: list[float] | None = None,
) -> dict:
    """CFD (or synthetic) at each speed; returns table for spec sheet."""
    out_dir.mkdir(parents=True, exist_ok=True)
    speeds = speeds_mph or fluid.get("speed_sweep_mph") or DEFAULT_SWEEP_MPH
    rows: list[dict] = []

    for mph in speeds:
        f = {**fluid, "speed_mph": mph, "velocity_ms": mph_to_ms(mph)}
        case = out_dir / f"case_{int(mph)}mph"
        run_case(case, f, stl=combined_stl)
        mpath = case / "metrics.json"
        if mpath.exists():
            metrics = json.loads(mpath.read_text())
        else:
            cd, cl = 0.28, 0.35
            metrics = estimate_aero_metrics(f, cd, cl)
        rows.append(
            {
                "speed_mph": mph,
                "cd": metrics.get("cd"),
                "cl": metrics.get("cl"),
                "downforce_lbs": metrics.get("downforce_n", 0) / 4.44822,
                "drag_lbs": metrics.get("drag_n", 0) / 4.44822,
            }
        )

    # Estimate top speed impact (simplified: drag power balance vs baseline)
    baseline_cd = float(fluid.get("baseline_cd", 0.32))
    vmax_stock = float(fluid.get("vmax_stock_mph", 130))
    cd_130 = next((r["cd"] for r in rows if r["speed_mph"] == vmax_stock), rows[-1]["cd"])
    drag_ratio = (cd_130 or 0.3) / baseline_cd
    vmax_with_wing = vmax_stock / (drag_ratio**0.333) if drag_ratio > 0 else vmax_stock

    result = {
        "rows": rows,
        "vmax_stock_mph": vmax_stock,
        "vmax_estimated_with_aero_mph": round(vmax_with_wing, 1),
        "note": "Top speed estimate uses Cd ratio vs stock baseline; full powertrain model not included.",
    }
    write_json(out_dir / "speed_sweep.json", result)
    return result
