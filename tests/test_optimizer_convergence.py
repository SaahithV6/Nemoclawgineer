from nemoclaw.models import Constraint, DesignParam, JobSpec, JobState, Objective
from nemoclaw.optimizer import _candidate_params, _feasible, _objective_value


def test_objective_minimize_mass():
    spec = JobSpec(objectives=[Objective(metric="mass_kg", sense="minimize")])
    assert _objective_value(spec, {"mass_kg": 0.5}) == 0.5


def test_constraint_stress():
    spec = JobSpec(
        constraints=[Constraint(metric="max_stress_mpa", op="le", value=200)],
    )
    assert _feasible(spec, {"max_stress_mpa": 180})
    assert not _feasible(spec, {"max_stress_mpa": 250})


def test_candidate_params_count():
    spec = JobSpec(
        design_params=[DesignParam(name="thickness_mm", min=2, max=10, initial=5)],
    )
    cands = _candidate_params(spec, {"thickness_mm": 5}, 0.3)
    assert len(cands) >= 1
    assert all(2 <= c["thickness_mm"] <= 10 for c in cands)


def test_plateau_logic_fields():
    state = JobState(
        job_id="abc",
        spec=JobSpec(user_request="test"),
    )
    assert state.passes == []
