from __future__ import annotations

"""
Run CFD and FEA on the same mesh in parallel (Brev 64 CPU / 512 GB RAM).
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from openclaw_engineering.config import load_defaults
from openclaw_engineering.models import Discipline, JobSpec


def run_cfd_branch(job_id: str, spec: JobSpec, stl_path: Path, work: Path) -> dict[str, Any]:
    from openclaw_engineering.tools.openfoam import run_case
    from openclaw_engineering.tools.openfoam import extract_cfd_metrics

    case_dir = work / "openfoam_parallel"
    run_case(case_dir=case_dir, fluid=spec.fluid, stl=stl_path)
    metrics_path = work / "cfd_metrics.json"
    metrics = extract_cfd_metrics(case_dir=case_dir, out_json=metrics_path)
    return {"discipline": "cfd", "metrics": metrics, "case_dir": str(case_dir)}


def run_fea_branch(job_id: str, spec: JobSpec, stl_path: Path, work: Path) -> dict[str, Any]:
    from openclaw_engineering.tools.gmsh import mesh_stl
    from openclaw_engineering.tools.calculix import run as ccx_run
    from openclaw_engineering.tools.fea import extract_metrics

    fea_work = work / "fea_parallel"
    fea_work.mkdir(exist_ok=True)
    inp = fea_work / "model.inp"
    mesh_stl(stl_path, float(spec.mesh_size or 3.0), inp)
    results = ccx_run(inp, spec.loads, fea_work / "ccx")
    metrics_path = fea_work / "metrics.json"
    metrics = extract_metrics(results_dir=results, out_json=metrics_path)
    return {"discipline": "fea", "metrics": metrics}


def run_parallel_physics(
    job_id: str,
    spec: JobSpec,
    stl_path: Path,
    *,
    run_cfd: bool = True,
    run_fea: bool = True,
) -> dict[str, Any]:
    """Execute CFD and FEA concurrently when both are requested."""
    work = Path(spec.input_stl or "").parent if spec.input_stl else None
    from openclaw_engineering.store import job_dir

    work = job_dir(job_id) / "work" / "parallel_physics"
    work.mkdir(parents=True, exist_ok=True)

    defaults = load_defaults()
    res = defaults.get("resources", {})
    max_workers = int(res.get("parallel_physics_workers", 2))

    tasks: list[tuple[str, Any]] = []
    out: dict[str, Any] = {"combined_metrics": {}, "branches": {}}

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {}
        if run_cfd and spec.discipline == Discipline.CFD:
            futs[ex.submit(run_cfd_branch, job_id, spec, stl_path, work)] = "cfd"
        if run_fea and (spec.discipline == Discipline.FEA or spec.run_wing_fea):
            futs[ex.submit(run_fea_branch, job_id, spec, stl_path, work)] = "fea"
        for fut in as_completed(futs):
            label = futs[fut]
            try:
                out["branches"][label] = fut.result()
                out["combined_metrics"].update(out["branches"][label].get("metrics", {}))
            except Exception as exc:
                out["branches"][label] = {"error": str(exc)}
    return out
