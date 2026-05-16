from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from openclaw_engineering.config import get_settings
from openclaw_engineering.delivery.openclaw_notify import notify_openclaw_agent, write_delivery_manifest
from openclaw_engineering.feasibility import apply_feasibility_to_spec
from openclaw_engineering.integrations.onshape import pull_from_onshape, push_to_onshape
from openclaw_engineering.models import Discipline, JobMode, JobSpec, JobState, JobStatus, PartCategory, SpeedSweepRow
from openclaw_engineering.optimizer import run_optimization
from openclaw_engineering.optuna_optimizer import run_optuna_optimization
from openclaw_engineering.parallel_physics import run_parallel_physics
from openclaw_engineering.planner import normalize_spec, plan_job_sync
from openclaw_engineering.report import finalize_artifacts
from openclaw_engineering.runner import load_flow_template, run_flow
from openclaw_engineering.store import (
    artifact_path,
    copy_input_stl,
    create_job,
    job_dir,
    load_state,
    save_state,
    write_flow_snapshot,
)
from openclaw_engineering.tools.speed_sweep import run_speed_sweep
from openclaw_engineering.tools.wing_fea import stress_test_wing

_active: dict[str, threading.Thread] = {}


def _body_stl_path(state: JobState) -> Path | None:
    p = job_dir(state.job_id) / "input.stl"
    return p if p.exists() else None


def _apply_mount_feasibility(state: JobState) -> None:
    body = _body_stl_path(state)
    if not body:
        return
    spec = state.spec
    spec.geometry_spec, meta = apply_feasibility_to_spec(
        spec.geometry_spec,
        body_stl=body,
        fluid=spec.fluid,
    )
    spec.geometry_spec["_fluid"] = spec.fluid
    spec.feasibility = meta
    state.spec = spec
    save_state(state)


def _deliver_results(state: JobState, stl_path: Path) -> None:
    finalize_artifacts(state, stl_path)
    report = artifact_path(state.job_id, "REPORT.md")
    result = artifact_path(state.job_id, "result.stl")
    metrics = artifact_path(state.job_id, "metrics.json")
    atts = [p for p in (report, result, metrics) if p.exists()]

    if state.spec.onshape:
        meta = push_to_onshape(result, state.spec.onshape, state.spec.onshape.part_name)
        state.message = f"OnShape push: {meta.get('status', 'unknown')}"
        save_state(state)

    email = state.spec.notify_email or get_settings().openclaw_engineering_notify_email
    write_delivery_manifest(state.job_id, email, None)
    hook = notify_openclaw_agent(
        state.job_id,
        state.spec.user_request,
        notify_email=email,
    )
    state.message = (state.message or "") + f" | Delivery: {hook.get('status')}"
    save_state(state)


def _post_process(state: JobState, result: dict) -> None:
    spec = state.spec
    work = job_dir(state.job_id) / "work"
    combined = work / "combined.stl"
    if not combined.exists():
        combined = Path(result.get("stl_path", work / "combined.stl"))
    addon = work / "addon.stl"

    def sweep_task():
        if spec.run_speed_sweep and spec.discipline == Discipline.CFD:
            return run_speed_sweep(combined, spec.fluid, work / "speed_sweep")

    def parallel_task():
        if spec.run_parallel_physics and combined.exists():
            return run_parallel_physics(
                state.job_id,
                spec,
                combined,
                run_cfd=spec.discipline == Discipline.CFD,
                run_fea=spec.run_wing_fea or spec.discipline == Discipline.FEA,
            )
        return None

    def wing_fea_task():
        if spec.run_wing_fea and addon.exists() and spec.part_category == PartCategory.WING:
            return stress_test_wing(addon, spec.loads, work / "wing_fea")
        return None

    with ThreadPoolExecutor(max_workers=3) as ex:
        f_sweep = ex.submit(sweep_task) if spec.run_speed_sweep else None
        f_par = ex.submit(parallel_task) if spec.run_parallel_physics else None
        f_fea = ex.submit(wing_fea_task) if spec.run_wing_fea else None

        if f_sweep:
            state.stage = "speed_sweep"
            save_state(state)
            try:
                sweep = f_sweep.result()
                if sweep:
                    state.speed_sweep = [SpeedSweepRow.model_validate(r) for r in sweep["rows"]]
                    state.vmax_estimated_mph = sweep.get("vmax_estimated_with_aero_mph")
            except Exception:
                pass

        if f_par:
            state.stage = "parallel_physics"
            save_state(state)
            try:
                state.spec.cad_params["parallel_physics"] = f_par.result()
            except Exception:
                pass

        if f_fea:
            state.stage = "wing_fea"
            save_state(state)
            try:
                fea = f_fea.result()
                if fea and not fea.get("feasible"):
                    fea2 = stress_test_wing(
                        addon,
                        {**spec.loads, "mesh_size": 2.5},
                        work / "wing_fea_reinforced",
                        reinforce=True,
                    )
                    fea["reinforcement_pass"] = fea2
                state.wing_fea = fea or {}
            except Exception:
                pass

    save_state(state)


def _run_analyze(state: JobState) -> JobState:
    _apply_mount_feasibility(state)
    params = {**{dp.name: dp.initial for dp in state.spec.design_params}, **state.spec.cad_params}
    state.status = JobStatus.RUNNING
    state.stage = "analyze"
    save_state(state)
    result = run_flow(state.job_id, state.spec, params)
    state.stop_reason = "analysis_complete"
    state.status = JobStatus.COMPLETED
    _post_process(state, result)
    _deliver_results(state, result["stl_path"])
    return state


def _execute_job(state: JobState) -> None:
    try:
        jd = job_dir(state.job_id)
        if state.spec.onshape:
            pulled = pull_from_onshape(jd, state.spec.onshape)
            if pulled:
                state.spec.input_stl = str(pulled)
                save_state(state)

        _apply_mount_feasibility(state)

        if state.spec.mode == JobMode.ANALYZE:
            _run_analyze(state)
            return

        if state.spec.mode == JobMode.OPTIMIZE:
            if state.spec.use_optuna and state.spec.discipline == Discipline.CFD:
                run_optuna_optimization(state)
            else:
                run_optimization(state)
            params = state.best_params or {dp.name: dp.initial for dp in state.spec.design_params}
            params = {**params, **{k: v for k, v in state.spec.cad_params.items() if isinstance(v, (int, float))}}
            result = run_flow(state.job_id, state.spec, params)
            _post_process(state, result)
            _deliver_results(state, result["stl_path"])
            return

        params = {**state.spec.cad_params, **{dp.name: dp.initial for dp in state.spec.design_params}}
        state.status = JobStatus.RUNNING
        state.stage = "generate"
        save_state(state)
        result = run_flow(state.job_id, state.spec, params)
        state.stop_reason = "generated"
        state.status = JobStatus.COMPLETED
        _post_process(state, result)
        _deliver_results(state, result["stl_path"])
    except Exception as exc:
        state.status = JobStatus.FAILED
        state.error = str(exc)
        state.stage = "failed"
        save_state(state)


def submit_job(
    user_request: str,
    spec: JobSpec | None = None,
    input_stl: Path | None = None,
    session_id: str | None = None,
    notify_email: str | None = None,
) -> JobState:
    stl_path = str(input_stl) if input_stl else None
    if spec is None:
        spec = plan_job_sync(user_request, stl_path)
    else:
        spec = normalize_spec(spec, user_request, stl_path)
    spec.session_id = session_id or spec.session_id
    if notify_email:
        spec.notify_email = notify_email

    if spec.needs_clarification:
        state = create_job(spec)
        state.status = JobStatus.AWAITING_USER
        state.stage = "clarification"
        state.pending_questions = spec.needs_clarification
        state.message = spec.needs_clarification[0].question
        save_state(state)
        return state

    state = create_job(spec)
    state.status = JobStatus.PLANNING
    state.stage = "planning"
    save_state(state)

    if input_stl and input_stl.exists():
        copy_input_stl(state.job_id, input_stl)
        spec.input_stl = str(job_dir(state.job_id) / "input.stl")
    elif spec.input_stl:
        p = Path(spec.input_stl)
        if p.exists():
            copy_input_stl(state.job_id, p)
            spec.input_stl = str(job_dir(state.job_id) / "input.stl")
    state.spec = spec
    save_state(state)

    write_flow_snapshot(state.job_id, load_flow_template(spec.flow_template))

    t = threading.Thread(target=_execute_job, args=(state,), daemon=True)
    _active[state.job_id] = t
    t.start()
    return state


def resume_job_after_clarification(state: JobState) -> JobState:
    state.status = JobStatus.PLANNING
    state.pending_questions = []
    state.stage = "planning"
    save_state(state)
    t = threading.Thread(target=_execute_job, args=(state,), daemon=True)
    _active[state.job_id] = t
    t.start()
    return state


def get_job(job_id: str) -> JobState | None:
    return load_state(job_id)
