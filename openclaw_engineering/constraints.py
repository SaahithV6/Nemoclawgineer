from __future__ import annotations

"""
Validate JobSpec and build executor-driven Discord questionnaires.
"""

from openclaw_engineering.clarification import build_clarification
from openclaw_engineering.models import (
    DeliverableScope,
    DesignParam,
    Discipline,
    JobMode,
    JobSpec,
    PartCategory,
)
from openclaw_engineering.sculpt.registry import infer_sculpt_method
from openclaw_engineering.tools.geometry_catalog import (
    design_params_from_geometry_spec,
    ensure_geometry_spec,
    infer_part_category,
)

_CFD_FLOWS = {"analyze_cfd.yaml", "cfd_wing_optimize.yaml"}
_FEA_FLOWS = {"optimize_fea.yaml"}


def _normalize_template_name(name: str) -> str:
    n = (name or "").strip()
    if not n:
        return ""
    return n if n.endswith(".yaml") else f"{n}.yaml"


def _recommended_flow(spec: JobSpec, text: str) -> str:
    if spec.discipline == Discipline.CFD:
        if spec.mode == JobMode.ANALYZE or ("analyze" in text and "optim" not in text):
            return "analyze_cfd.yaml"
        return "cfd_wing_optimize.yaml"
    return "optimize_fea.yaml"


def _is_flow_compatible(flow_name: str, discipline: Discipline) -> bool:
    if discipline == Discipline.CFD:
        return flow_name in _CFD_FLOWS
    return flow_name in _FEA_FLOWS


def infer_missing_from_request(spec: JobSpec) -> JobSpec:
    text = spec.user_request.lower()

    if spec.part_category == PartCategory.CUSTOM:
        spec.part_category = infer_part_category(spec.user_request)

    if any(p in text for p in ("only the wing", "wing only", "only the bracket", "part only", "addon only")):
        spec.deliverable_scope = DeliverableScope.ADDON_ONLY
    elif "full car" in text or "full assembly" in text or "with the body" in text:
        spec.deliverable_scope = DeliverableScope.FULL_ASSEMBLY

    cat = spec.part_category.value
    spec.geometry_spec = ensure_geometry_spec(spec.geometry_spec, spec.user_request, cat)
    if not spec.geometry_spec.get("sculpt_method"):
        spec.geometry_spec["sculpt_method"] = infer_sculpt_method(
            spec.user_request, spec.discipline.value
        )
    from openclaw_engineering.sculpt.registry import SCULPT_METHODS

    sm = SCULPT_METHODS.get(spec.geometry_spec["sculpt_method"])
    if sm and not spec.geometry_spec.get("params"):
        spec.geometry_spec["params"] = {
            k: v.get("default") for k, v in sm.param_schema.items() if isinstance(v, dict) and "default" in v
        }

    if "analyze" in text and "optim" not in text:
        spec.mode = JobMode.ANALYZE

    resolved_template = _normalize_template_name(spec.flow_template)
    if not resolved_template or not _is_flow_compatible(resolved_template, spec.discipline):
        spec.flow_template = _recommended_flow(spec, text)
    else:
        spec.flow_template = resolved_template

    mfg = dict(spec.manufacturing)
    gs = spec.geometry_spec
    if gs.get("material"):
        mfg.setdefault("material", gs["material"])
    if gs.get("tolerance_mm") is not None:
        mfg.setdefault("tolerance_mm", gs["tolerance_mm"])
    if gs.get("machining_notes"):
        mfg.setdefault("machining_notes", gs["machining_notes"])
    spec.manufacturing = mfg

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
    """Safety defaults + design params from geometry_spec; no rigid part-type lock-in."""
    if not spec.design_params:
        for dp in design_params_from_geometry_spec(spec.geometry_spec):
            spec.design_params.append(
                DesignParam(
                    name=dp["name"],
                    min=float(dp["min"]),
                    max=float(dp["max"]),
                    initial=float(dp["initial"]),
                )
            )

    if spec.part_category == PartCategory.AERO_KIT:
        spec.run_wing_fea = False

    spec.agent_review_each_pass = True

    pending = build_clarification(spec)
    if pending:
        spec.needs_clarification = pending

    return spec
