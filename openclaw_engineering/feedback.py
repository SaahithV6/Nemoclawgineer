from __future__ import annotations

from openclaw_engineering.models import AgentFeedback, Constraint, JobSpec, PassRecord


def build_agent_feedback(spec: JobSpec, record: PassRecord) -> AgentFeedback:
    """Reduced CAE summary for Nemotron between optimization passes."""
    violations: list[str] = []
    for c in spec.constraints:
        val = record.metrics.get(c.metric)
        if val is None:
            continue
        if c.op == "le" and val > c.value:
            violations.append(f"{c.metric}={val:.4g} > {c.value} {c.unit}".strip())
        if c.op == "ge" and val < c.value:
            violations.append(f"{c.metric}={val:.4g} < {c.value} {c.unit}".strip())

    # CFD wing demo keys
    keys = ["cd", "cl", "downforce_n", "drag_n", "max_stress_mpa", "mass_kg"]
    slim = {k: round(record.metrics[k], 6) for k in keys if k in record.metrics}

    return AgentFeedback(
        pass_index=record.pass_index,
        metrics=slim,
        feasible=record.feasible and not violations,
        constraint_violations=violations,
        recommendation="",
        suggest_stop=False,
        param_adjustments={},
    )
