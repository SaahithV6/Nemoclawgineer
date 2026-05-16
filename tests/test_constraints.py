from openclaw_engineering.constraints import enforce_agent_rules, infer_missing_from_request
from openclaw_engineering.models import JobSpec, Discipline, GeometryKind


def test_infer_cfd_wing():
    spec = infer_missing_from_request(
        JobSpec(user_request="optimize rear wing for downforce", discipline=Discipline.CFD)
    )
    assert spec.geometry_kind == GeometryKind.REAR_WING


def test_infer_downforce_kit():
    spec = infer_missing_from_request(
        JobSpec(user_request="full aero kit with splitter and diffuser", discipline=Discipline.CFD)
    )
    assert spec.geometry_kind == GeometryKind.DOWNFORCE_KIT


def test_enforce_no_optuna():
    spec = enforce_agent_rules(JobSpec(use_optuna=True))
    assert spec.use_optuna is False
