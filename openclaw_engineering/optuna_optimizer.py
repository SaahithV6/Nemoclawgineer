from __future__ import annotations

from typing import Callable

import optuna

from openclaw_engineering.config import get_settings, load_defaults
from openclaw_engineering.models import JobSpec, JobState, JobStatus, PassRecord
from openclaw_engineering.runner import run_flow
from openclaw_engineering.store import is_cancelled, save_state
from openclaw_engineering.optimizer import _feasible, _objective_value
from openclaw_engineering.agent import review_pass_sync
from openclaw_engineering.tools.cfd_metrics import estimate_aero_metrics


def run_optuna_optimization(
    state: JobState,
    on_progress: Callable[[JobState], None] | None = None,
) -> JobState:
    spec = state.spec
    settings = get_settings()
    n_trials = min(
        settings.openclaw_engineering_optuna_trials,
        spec.max_passes or int(load_defaults().get("optimization", {}).get("max_passes", 3)) * 4,
    )

    state.status = JobStatus.RUNNING
    state.stage = "optuna"
    save_state(state)

    pass_idx = 0

    def objective(trial: optuna.Trial) -> float:
        nonlocal pass_idx
        if is_cancelled(state.job_id):
            raise optuna.exceptions.OptunaError("cancelled")

        params: dict[str, float] = {}
        for dp in spec.design_params:
            params[dp.name] = trial.suggest_float(dp.name, dp.min, dp.max)
        for k, v in spec.cad_params.items():
            if isinstance(v, (int, float)):
                params[k] = float(v)

        pass_idx += 1
        state.stage = f"optuna_trial_{pass_idx}"
        save_state(state)
        if on_progress:
            on_progress(state)

        result = run_flow(state.job_id, spec, params)
        metrics = result["metrics"]
        if spec.discipline.value == "cfd" and "cd" in metrics:
            metrics.update(
                estimate_aero_metrics(spec.fluid, metrics["cd"], metrics.get("cl", 0.1))
            )

        obj = _objective_value(spec, metrics)
        ok = _feasible(spec, metrics)

        # Target downforce constraint (wing demo)
        target_df = spec.fluid.get("target_downforce_lbs")
        if target_df:
            from openclaw_engineering.tools.cfd_metrics import downforce_error

            obj += downforce_error(metrics, float(target_df)) * 10.0

        rec = PassRecord(
            pass_index=pass_idx,
            params=params,
            metrics=metrics,
            feasible=ok,
            objective_value=obj,
        )
        if spec.agent_review_each_pass:
            fb = review_pass_sync(spec, state, rec)
            rec.agent_note = fb.recommendation
            state.agent_log.append(fb)
            if fb.suggest_stop:
                trial.study.stop()

        state.passes.append(rec)
        if obj < state.best_params.get("_best_obj", float("inf")):
            state.best_params = {**params, "_best_obj": obj}
        save_state(state)
        if on_progress:
            on_progress(state)
        return obj

    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=n_trials, n_jobs=1, show_progress_bar=False)

    best = {k: v for k, v in state.best_params.items() if k != "_best_obj"}
    state.best_params = best
    state.stop_reason = "optuna_complete"
    state.status = JobStatus.COMPLETED
    state.stage = "done"
    save_state(state)
    return state
