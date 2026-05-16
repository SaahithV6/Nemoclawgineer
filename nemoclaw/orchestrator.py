from __future__ import annotations

import shutil
import threading
from pathlib import Path

from nemoclaw.models import Discipline, JobMode, JobSpec, JobState, JobStatus
from nemoclaw.optimizer import run_optimization
from nemoclaw.planner import plan_job_sync
from nemoclaw.report import finalize_artifacts
from nemoclaw.runner import load_flow_template, run_flow
from nemoclaw.store import copy_input_stl, create_job, job_dir, load_state, save_state, write_flow_snapshot

_active: dict[str, threading.Thread] = {}


def _run_analyze(state: JobState) -> JobState:
    params = {dp.name: dp.initial for dp in state.spec.design_params} or {"thickness_scale": 1.0}
    state.status = JobStatus.RUNNING
    state.stage = "analyze"
    save_state(state)
    result = run_flow(state.job_id, state.spec, params)
    state.passes = []
    state.stop_reason = "analysis_complete"
    state.status = JobStatus.COMPLETED
    state.best_params = params
    save_state(state)
    finalize_artifacts(state, result["stl_path"])
    return state


def _execute_job(state: JobState) -> None:
    try:
        if state.spec.mode == JobMode.ANALYZE or (
            state.spec.discipline == Discipline.CFD and state.spec.mode != JobMode.OPTIMIZE
        ):
            _run_analyze(state)
            return

        if state.spec.mode == JobMode.OPTIMIZE:
            run_optimization(state)
            params = state.best_params or {dp.name: dp.initial for dp in state.spec.design_params}
            result = run_flow(state.job_id, state.spec, params)
            finalize_artifacts(state, result["stl_path"])
            return

        # generate / collab: single flow pass
        params = {dp.name: dp.initial for dp in state.spec.design_params} or {"thickness_scale": 1.0}
        state.status = JobStatus.RUNNING
        state.stage = "generate"
        save_state(state)
        result = run_flow(state.job_id, state.spec, params)
        state.stop_reason = "generated"
        state.status = JobStatus.COMPLETED
        finalize_artifacts(state, result["stl_path"])
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
) -> JobState:
    stl_path = str(input_stl) if input_stl else None
    if spec is None:
        spec = plan_job_sync(user_request, stl_path)
    spec.user_request = user_request or spec.user_request
    spec.session_id = session_id or spec.session_id

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

    flow = load_flow_template(spec.flow_template)
    write_flow_snapshot(state.job_id, flow)

    t = threading.Thread(target=_execute_job, args=(state,), daemon=True)
    _active[state.job_id] = t
    t.start()
    return state


def get_job(job_id: str) -> JobState | None:
    return load_state(job_id)
