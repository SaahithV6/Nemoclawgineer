from openclaw_engineering.constraints import enforce_agent_rules, infer_missing_from_request
from openclaw_engineering.models import DeliverableScope, Discipline, JobSpec, PartCategory


def test_infer_wing_only_deliverable():
    spec = infer_missing_from_request(
        JobSpec(
            user_request="create a new file containing only the wing",
            discipline=Discipline.CFD,
        )
    )
    assert spec.deliverable_scope == DeliverableScope.ADDON_ONLY
    assert spec.part_category == PartCategory.WING


def test_infer_bracket():
    spec = infer_missing_from_request(
        JobSpec(user_request="L bracket with gussets 90mm legs", discipline=Discipline.FEA)
    )
    assert spec.part_category == PartCategory.BRACKET
    assert spec.geometry_spec.get("features")


def test_clarification_when_incomplete():
    spec = enforce_agent_rules(JobSpec(user_request="make something", discipline=Discipline.FEA))
    assert len(spec.needs_clarification) > 0


def test_enforce_no_optuna():
    spec = enforce_agent_rules(JobSpec(use_optuna=True))
    assert spec.use_optuna is False
