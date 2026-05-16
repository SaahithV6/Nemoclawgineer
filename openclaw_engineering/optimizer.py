from __future__ import annotations

import copy
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from openclaw_engineering.config import load_defaults
from openclaw_engineering.models import Constraint, Discipline, JobSpec, JobState, JobStatus, PassRecord
from openclaw_engineering.agent import review_pass_sync
from openclaw_engineering.runner import run_flow
from openclaw_engineering.store import is_cancelled, save_state


def _objective_value(spec: JobSpec, metrics: dict[str, float]) -> float:
    metric = spec.default_objective_metric()
    val = metrics.get(metric)
    if val is None:
        if spec.discipline == Discipline.CFD:
            val = metrics.get("cd", 1.0)
        else:
            val = metrics.get("mass_kg", 1.0)
    sense = "minimize"
    if spec.objectives:
        sense = spec.objectives[0].sense
    return float(val) if sense == "minimize" else -float(val)


def _feasible(spec: JobSpec, metrics: dict[str, float]) -> bool:
    for c in spec.constraints:
        v = metrics.get(c.metric)
        if v is None:
            continue
        if c.op == "le" and v > c.value:
            return False
        if c.op == "ge" and v < c.value:
            return False
        if c.op == "eq" and abs(v - c.value) > 1e-6:
            return False
    return True


def _candidate_params(spec: JobSpec, center: dict[str, float], spread: float) -> list[dict[str, float]]:
    if not spec.design_params:
        return [{"thickness_scale": 1.0}]
    candidates: list[dict[str, float]] = []
    n = int(load_defaults().get("optimization", {}).get("parallel_candidates", 4))
    for i in range(n):
        p = {}
        for dp in spec.design_params:
            t = i / max(n - 1, 1)
            val = dp.min + t * (dp.max - dp.min)
            if center:
                val = center.get(dp.name, dp.initial) + spread * (val - center.get(dp.name, dp.initial))
            p[dp.name] = max(dp.min, min(dp.max, val))
            if dp.name == "thickness_mm" and "thickness_scale" not in p:
                p["thickness_scale"] = p[dp.name] / max(dp.initial, 0.1)
        candidates.append(p)
    return candidates


def run_optimization(
    state: JobState,
    on_progress: Callable[[JobState], None] | None = None,
) -> JobState:
    spec = state.spec
    defaults = load_defaults()
    opt = defaults.get("optimization", {})
    max_passes = spec.max_passes or int(opt.get("max_passes", 3))
    conv = opt.get("convergence", {})
    min_gain = float(conv.get("min_relative_gain", 0.02))
    plateau_needed = int(conv.get("plateau_passes", 2))

    state.status = JobStatus.RUNNING
    state.stage = "optimize"
    save_state(state)
    if on_progress:
        on_progress(state)

    best_obj: float | None = None
    best_params: dict[str, float] = {}
    plateau = 0
    center: dict[str, float] = {dp.name: dp.initial for dp in spec.design_params}

    for pass_idx in range(1, max_passes + 1):
        if is_cancelled(state.job_id):
            state.stop_reason = "user_stop"
            state.status = JobStatus.CANCELLED
            save_state(state)
            return state

        state.stage = f"solve_pass_{pass_idx}"
        state.message = f"Running pass {pass_idx}/{max_passes}"
        save_state(state)
        if on_progress:
            on_progress(state)

        spread = 0.5 / pass_idx
        candidates = _candidate_params(spec, center, spread)

        def eval_one(params: dict[str, float]) -> tuple[dict[str, float], dict[str, float], float, bool]:
            from openclaw_engineering.feasibility import apply_feasibility_to_spec
            from openclaw_engineering.store import job_dir

            body = job_dir(state.job_id) / "input.stl"
            if body.exists():
                spec.geometry_spec, _ = apply_feasibility_to_spec(
                    {**spec.geometry_spec, "params": {**spec.geometry_spec.get("params", {}), **params}},
                    body_stl=body,
                    fluid=spec.fluid,
                )
                spec.geometry_spec["_fluid"] = spec.fluid
            result = run_flow(state.job_id, spec, params)
            metrics = result["metrics"]
            obj = _objective_value(spec, metrics)
            ok = _feasible(spec, metrics)
            return params, metrics, obj, ok

        parallel = int(opt.get("parallel_candidates", 4))
        results: list[tuple[dict[str, float], dict[str, float], float, bool]] = []

        if parallel > 1 and len(candidates) > 1:
            with ThreadPoolExecutor(max_workers=min(parallel, len(candidates))) as ex:
                futs = {ex.submit(eval_one, c): c for c in candidates}
                for fut in as_completed(futs):
                    results.append(fut.result())
        else:
            for c in candidates:
                results.append(eval_one(c))

        pass_best = min(results, key=lambda r: r[2])
        params, metrics, obj, ok = pass_best
        rel_gain: float | None = None
        if best_obj is not None and best_obj > 0:
            rel_gain = (best_obj - obj) / abs(best_obj)

        rec = PassRecord(
            pass_index=pass_idx,
            params=params,
            metrics=metrics,
            feasible=ok,
            objective_value=obj,
            relative_gain=rel_gain,
        )

        state.passes.append(rec)

        improved = best_obj is None or obj < best_obj
        if improved:
            if best_obj is not None and rel_gain is not None and rel_gain < min_gain:
                plateau += 1
            else:
                plateau = 0
            best_obj = obj
            best_params = copy.deepcopy(params)
            center = copy.deepcopy(params)
        else:
            plateau += 1

        agent_center: dict[str, float] | None = None
        if spec.agent_review_each_pass:
            fb = review_pass_sync(spec, state, rec)
            rec.agent_note = fb.recommendation
            state.agent_log.append(fb)
            seed = copy.deepcopy(best_params or params)
            agent_center = _apply_agent_adjustments(seed, fb.param_adjustments, spec)
            if fb.suggest_stop:
                state.best_params = best_params or params
                state.stop_reason = "agent_converged"
                break

        if agent_center is not None:
            center = agent_center

        state.best_params = best_params
        save_state(state)
        if on_progress:
            on_progress(state)

        if ok and plateau >= plateau_needed:
            state.stop_reason = "constraints_met" if ok else "converged"
            break
        if plateau >= plateau_needed:
            state.stop_reason = "converged"
            break

    if not state.stop_reason:
        state.stop_reason = "max_passes"

    state.status = JobStatus.COMPLETED
    state.stage = "done"
    save_state(state)
    return state


def _apply_agent_adjustments(
    seed: dict[str, float],
    adjustments: dict[str, float],
    spec: JobSpec,
) -> dict[str, float]:
    """Merge Nemotron param_adjustments into next-pass CAD seed (clamped to design_params)."""
    if not adjustments:
        return seed
    merged = copy.deepcopy(seed)
    bounds = {dp.name: dp for dp in spec.design_params}
    for key, val in adjustments.items():
        try:
            v = float(val)
        except (TypeError, ValueError):
            continue
        if key in bounds:
            dp = bounds[key]
            merged[key] = max(dp.min, min(dp.max, v))
        else:
            merged[key] = v
    return merged
