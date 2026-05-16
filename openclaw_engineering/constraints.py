from __future__ import annotations

"""
Runtime enforcement of rules the OpenClaw agent must infer per demo.
Documented in skills/openclaw-engineering/SKILL.md — not hardcoded to one vehicle.
"""

from openclaw_engineering.models import (
    ClarificationQuestion,
    DesignParam,
    Discipline,
    GeometryKind,
    JobMode,
    JobSpec,
)
from openclaw_engineering.tools.geometry_catalog import infer_geometry_kind


def infer_missing_from_request(spec: JobSpec) -> JobSpec:
    text = spec.user_request.lower()
    if spec.geometry_kind is None or spec.geometry_kind == GeometryKind.REAR_WING:
        if not spec.cad_params.get("kind"):
            spec.geometry_kind = infer_geometry_kind(spec.user_request)

    if spec.discipline == Discipline.CFD and not spec.flow_template.endswith(".yaml"):
        spec.flow_template = "cfd_wing_optimize.yaml"
    if spec.discipline == Discipline.FEA and spec.flow_template == "optimize_fea.yaml":
        pass
    elif spec.discipline == Discipline.FEA and "optimize" in text:
        spec.flow_template = "optimize_fea.yaml"

    if "analyze" in text and "optim" not in text:
        spec.mode = JobMode.ANALYZE

    spec.cad_params["kind"] = spec.geometry_kind.value

    if spec.run_speed_sweep and spec.discipline == Discipline.CFD:
        spec.fluid.setdefault("vmax_stock_mph", spec.fluid.get("vmax_stock_mph", 130))
        spec.fluid.setdefault(
            "speed_sweep_mph",
            spec.fluid.get(
                "speed_sweep_mph",
                [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130],
            ),
        )

    return spec


def enforce_agent_rules(spec: JobSpec) -> JobSpec:
    """Reject unsafe agent output; clamp params."""
    if spec.geometry_kind == GeometryKind.REAR_WING:
        if not spec.design_params:
            spec.design_params = [
                DesignParam(name="angle_of_attack_deg", min=-2, max=16, initial=8),
                DesignParam(name="chord_mm", min=180, max=450, initial=280),
                DesignParam(name="span_mm", min=600, max=1600, initial=1200),
            ]
        for dp in spec.design_params:
            dp.max = min(dp.max, 500 if "mm" in dp.name else 20)
    elif spec.geometry_kind == GeometryKind.DOWNFORCE_KIT:
        spec.flow_template = spec.flow_template or "cfd_wing_optimize.yaml"
        spec.run_wing_fea = False

    spec.use_optuna = False
    spec.agent_review_each_pass = True
    spec = fea_load_clarification(spec)
    return spec


def fea_load_clarification(spec: JobSpec) -> JobSpec:
    """Backstop when the agent submits FEA without loads — ask in Discord before running."""
    if spec.discipline != Discipline.FEA:
        return spec
    if spec.needs_clarification:
        return spec

    loads = spec.loads or {}
    has_force = any(k in loads for k in ("force_n", "magnitude", "force_vector"))
    has_stress_limit = any(c.metric in ("max_stress_mpa", "stress_mpa") for c in spec.constraints)

    questions: list[ClarificationQuestion] = []
    if not has_force:
        questions.append(
            ClarificationQuestion(
                field="loads.force_n",
                question=(
                    "What loads should this part see? (e.g. 500 N tensile, 2 kN shear, "
                    "bolt preload, or describe the mounting / operating case.)"
                ),
            )
        )
    if not has_stress_limit:
        questions.append(
            ClarificationQuestion(
                field="constraints.max_stress_mpa",
                question=(
                    "What is the allowable stress (MPa) or material? "
                    "(e.g. aluminum 6061-T6 ~275 MPa yield, steel ~350 MPa.)"
                ),
            )
        )
    if not loads.get("fixed_faces") and not loads.get("constraint_hint"):
        questions.append(
            ClarificationQuestion(
                field="loads.constraint_hint",
                question="How is the part fixed? (e.g. one face bolted, two holes pinned, cantilever root.)",
            )
        )

    if questions:
        spec.needs_clarification = questions
    return spec
