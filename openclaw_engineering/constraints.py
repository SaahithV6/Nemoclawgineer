from __future__ import annotations

"""
Runtime enforcement of rules the OpenClaw agent must infer per demo.
Documented in skills/openclaw-engineering/SKILL.md — not hardcoded to one vehicle.
"""

from openclaw_engineering.models import (
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
    return spec
