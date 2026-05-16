from __future__ import annotations

import importlib
import re
from pathlib import Path
from typing import Any

import yaml

from nemoclaw.config import REPO_ROOT, load_defaults
from nemoclaw.models import JobSpec
from nemoclaw.store import job_dir

STEP_REGISTRY: dict[str, str] = {
    "nemoclaw.tools.freecad.deform_stl": "nemoclaw.tools.freecad",
    "nemoclaw.tools.gmsh.mesh_stl": "nemoclaw.tools.gmsh",
    "nemoclaw.tools.calculix.run": "nemoclaw.tools.calculix",
    "nemoclaw.tools.fea.extract_metrics": "nemoclaw.tools.fea",
    "nemoclaw.tools.openfoam.run_case": "nemoclaw.tools.openfoam",
    "nemoclaw.tools.cfd.extract_cfd_metrics": "nemoclaw.tools.cfd",
}


def _resolve(path: str, ctx: dict[str, Any]) -> Any:
    if not isinstance(path, str):
        return path
    m = re.fullmatch(r"\$\{(.+?)\}", path.strip())
    if m:
        key = m.group(1)
        if key in ctx:
            return ctx[key]
        cur: Any = ctx
        for part in key.split("."):
            if isinstance(cur, dict):
                cur = cur.get(part)
            else:
                cur = getattr(cur, part, None)
        return cur
    return path


def _resolve_mapping(obj: Any, ctx: dict[str, Any]) -> Any:
    if isinstance(obj, dict):
        return {k: _resolve_mapping(v, ctx) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_mapping(v, ctx) for v in obj]
    if isinstance(obj, str):
        full = re.fullmatch(r"\$\{(.+?)\}", obj)
        if full:
            return _resolve(obj, ctx)
        parts = re.split(r"(\$\{[^}]+\})", obj)
        if len(parts) == 1:
            return obj
        out = ""
        for p in parts:
            if p.startswith("${") and p.endswith("}"):
                out += str(_resolve(p, ctx))
            else:
                out += p
        return out
    return obj


def load_flow_template(name: str) -> dict[str, Any]:
    path = REPO_ROOT / "flows" / "templates" / name
    if not path.exists():
        path = REPO_ROOT / "flows" / "templates" / f"{name}.yaml"
    with path.open() as f:
        return yaml.safe_load(f)


def _call_step(run_path: str, kwargs: dict[str, Any]) -> Any:
    mod_name = STEP_REGISTRY.get(run_path, run_path.rsplit(".", 1)[0])
    fn_name = run_path.rsplit(".", 1)[-1]
    mod = importlib.import_module(mod_name)
    fn = getattr(mod, fn_name)
    return fn(**kwargs)


def run_flow(
    job_id: str,
    spec: JobSpec,
    params: dict[str, float],
    flow_name: str | None = None,
) -> dict[str, Any]:
    flow = load_flow_template(flow_name or spec.flow_template)
    work = job_dir(job_id) / "work"
    work.mkdir(exist_ok=True)

    defaults = load_defaults()
    mesh_size = spec.mesh_size
    if mesh_size is None:
        mesh_cfg = defaults.get("mesh", {})
        mesh_size = (
            mesh_cfg.get("fine_size_mm", 1.5)
            if not mesh_cfg.get("demo_coarse", True)
            else mesh_cfg.get("default_size_mm", 4.0)
        )

    stl_in = spec.input_stl
    if stl_in and not Path(stl_in).is_absolute():
        stl_in = str(job_dir(job_id) / Path(stl_in).name)
    if stl_in is None:
        stl_in = str(job_dir(job_id) / "input.stl")

    ctx: dict[str, Any] = {
        "job": {
            "input_stl": stl_in,
            "mesh_size": mesh_size,
            "loads": spec.loads,
            "fluid": spec.fluid,
            "params": params,
        },
        "params": params,
    }

    artifacts: dict[str, Path] = {}
    last_metrics: dict[str, float] = {}

    for step in flow.get("steps", []):
        step_id = step["id"]
        resolved_with = _resolve_mapping(step.get("with", {}), {**ctx, **artifacts})
        out_key = step.get("out", step_id)

        run_path = step["run"]
        if run_path == "nemoclaw.tools.freecad.deform_stl":
            out_path = work / "deformed.stl"
            _call_step(
                run_path,
                {
                    "stl_in": Path(resolved_with["stl"]),
                    "params": resolved_with.get("params", params),
                    "out_stl": out_path,
                },
            )
            artifacts["deformed.stl"] = out_path
        elif run_path == "nemoclaw.tools.gmsh.mesh_stl":
            stl = Path(resolved_with.get("stl", artifacts.get("deformed.stl", stl_in)))
            out_inp = work / f"{step_id}.inp"
            _call_step(
                run_path,
                {"stl": stl, "size": float(resolved_with.get("size", mesh_size)), "out_inp": out_inp},
            )
            artifacts["model.inp"] = out_inp
        elif run_path == "nemoclaw.tools.calculix.run":
            out_results = work / step_id
            _call_step(
                run_path,
                {
                    "inp": Path(resolved_with["inp"]),
                    "loads": resolved_with.get("loads", spec.loads),
                    "out_dir": out_results,
                },
            )
            artifacts["results/"] = out_results
        elif run_path == "nemoclaw.tools.fea.extract_metrics":
            out_json = work / "metrics.json"
            last_metrics = _call_step(
                run_path,
                {"results_dir": Path(resolved_with.get("results_dir", artifacts.get("results/", work))), "out_json": out_json},
            )
            artifacts["metrics.json"] = out_json
        elif run_path == "nemoclaw.tools.openfoam.run_case":
            case_dir = work / "openfoam"
            _call_step(
                run_path,
                {
                    "case_dir": case_dir,
                    "fluid": resolved_with.get("fluid", spec.fluid),
                    "stl": Path(resolved_with["stl"]) if resolved_with.get("stl") else None,
                },
            )
            artifacts["openfoam/"] = case_dir
        elif run_path == "nemoclaw.tools.cfd.extract_cfd_metrics":
            out_json = work / "metrics.json"
            last_metrics = _call_step(
                run_path,
                {"case_dir": Path(resolved_with.get("case_dir", artifacts.get("openfoam/", work))), "out_json": out_json},
            )
            artifacts["metrics.json"] = out_json
        else:
            raise ValueError(f"Unknown step: {run_path}")

        ctx[out_key] = str(artifacts.get(out_key, ""))
        ctx["artifacts"] = {k: str(v) for k, v in artifacts.items()}

    stl_out = artifacts.get("deformed.stl", Path(stl_in))
    return {
        "metrics": last_metrics,
        "stl_path": Path(stl_out),
        "artifacts": artifacts,
    }
