from __future__ import annotations

import importlib
import re
from pathlib import Path
from typing import Any

import yaml

from openclaw_engineering.config import REPO_ROOT, load_defaults
from openclaw_engineering.models import JobSpec
from openclaw_engineering.store import job_dir

STEP_REGISTRY: dict[str, str] = {
    "openclaw_engineering.tools.freecad.deform_stl": "openclaw_engineering.tools.freecad",
    "openclaw_engineering.tools.build123d_cad.generate_rear_wing": "openclaw_engineering.tools.build123d_cad",
    "openclaw_engineering.tools.build123d_cad.generate_geometry": "openclaw_engineering.tools.build123d_cad",
    "openclaw_engineering.tools.build123d_cad.attach_wing_to_body": "openclaw_engineering.tools.build123d_cad",
    "openclaw_engineering.tools.build123d_cad.resolve_deliverable_stl": "openclaw_engineering.tools.build123d_cad",
    "openclaw_engineering.tools.gmsh.mesh_stl": "openclaw_engineering.tools.gmsh",
    "openclaw_engineering.tools.calculix.run": "openclaw_engineering.tools.calculix",
    "openclaw_engineering.tools.fea.extract_metrics": "openclaw_engineering.tools.fea",
    "openclaw_engineering.tools.openfoam.run_case": "openclaw_engineering.tools.openfoam",
    "openclaw_engineering.tools.cfd.extract_cfd_metrics": "openclaw_engineering.tools.cfd",
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
            "params": {
                **params,
                "part_category": spec.part_category.value,
                **spec.cad_params,
            },
            "geometry_spec": spec.geometry_spec,
            "deliverable_scope": spec.deliverable_scope.value,
            "user_request": spec.user_request,
            "fluid": spec.fluid,
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
        if run_path == "openclaw_engineering.tools.freecad.deform_stl":
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
        elif run_path == "openclaw_engineering.tools.gmsh.mesh_stl":
            stl = Path(resolved_with.get("stl", artifacts.get("deformed.stl", stl_in)))
            out_inp = work / f"{step_id}.inp"
            _call_step(
                run_path,
                {"stl": stl, "size": float(resolved_with.get("size", mesh_size)), "out_inp": out_inp},
            )
            artifacts["model.inp"] = out_inp
        elif run_path == "openclaw_engineering.tools.calculix.run":
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
        elif run_path == "openclaw_engineering.tools.fea.extract_metrics":
            out_json = work / "metrics.json"
            last_metrics = _call_step(
                run_path,
                {"results_dir": Path(resolved_with.get("results_dir", artifacts.get("results/", work))), "out_json": out_json},
            )
            artifacts["metrics.json"] = out_json
        elif run_path == "openclaw_engineering.tools.openfoam.run_case":
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
        elif run_path == "openclaw_engineering.tools.cfd.extract_cfd_metrics":
            out_json = work / "metrics.json"
            last_metrics = _call_step(
                run_path,
                {"case_dir": Path(resolved_with.get("case_dir", artifacts.get("openfoam/", work))), "out_json": out_json},
            )
            artifacts["metrics.json"] = out_json
        elif run_path in (
            "openclaw_engineering.tools.build123d_cad.generate_rear_wing",
            "openclaw_engineering.tools.build123d_cad.generate_geometry",
        ):
            out_path = work / "addon.stl"
            gs = {
                **spec.geometry_spec,
                "_fluid": spec.fluid,
                "input_stl": stl_in if Path(stl_in).exists() else spec.input_stl,
            }
            merged = {**spec.cad_params, **params, "part_category": spec.part_category.value}
            _call_step(
                "openclaw_engineering.tools.build123d_cad.generate_geometry",
                {
                    "params": merged,
                    "out_stl": out_path,
                    "user_request": spec.user_request,
                    "geometry_spec": gs,
                },
            )
            artifacts["addon.stl"] = out_path
            artifacts["part.stl"] = out_path
        elif run_path in (
            "openclaw_engineering.tools.build123d_cad.attach_wing_to_body",
            "openclaw_engineering.tools.build123d_cad.resolve_deliverable_stl",
        ):
            out_path = work / "combined.stl"
            body = Path(resolved_with.get("body_stl", stl_in))
            if not body.exists():
                body = Path(stl_in)
            _call_step(
                "openclaw_engineering.tools.build123d_cad.resolve_deliverable_stl",
                {
                    "deliverable_scope": resolved_with.get(
                        "deliverable_scope", spec.deliverable_scope.value
                    ),
                    "addon_stl": Path(resolved_with.get("addon_stl", artifacts.get("addon.stl", out_path))),
                    "body_stl": body,
                    "out_stl": out_path,
                },
            )
            artifacts["combined.stl"] = out_path
        else:
            raise ValueError(f"Unknown step: {run_path}")

        ctx[out_key] = str(artifacts.get(out_key, ""))
        ctx["artifacts"] = {k: str(v) for k, v in artifacts.items()}

    stl_out = artifacts.get("combined.stl") or artifacts.get("deformed.stl") or Path(stl_in)
    return {
        "metrics": last_metrics,
        "stl_path": Path(stl_out),
        "artifacts": artifacts,
    }
