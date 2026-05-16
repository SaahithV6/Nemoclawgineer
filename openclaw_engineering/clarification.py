from __future__ import annotations

from typing import Any

from openclaw_engineering.models import ClarificationQuestion, DeliverableScope, Discipline, JobSpec, PartCategory


def _get_nested(data: dict[str, Any], path: str) -> Any:
    cur: Any = data
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def field_is_set(spec: JobSpec, field: str) -> bool:
    if field == "deliverable_scope":
        t = spec.user_request.lower()
        return any(
            p in t
            for p in (
                "addon only",
                "wing only",
                "only the wing",
                "bracket only",
                "full assembly",
                "with the body",
                "body only",
                "part file only",
            )
        )
    if field == "geometry_spec.sculpt_method":
        return bool((spec.geometry_spec or {}).get("sculpt_method"))
    if field == "part_category":
        return spec.part_category != PartCategory.CUSTOM
    if field == "notify_email":
        return bool(spec.notify_email)
    if field.startswith("geometry_spec."):
        rest = field[len("geometry_spec.") :]
        if rest == "description":
            return bool((spec.geometry_spec or {}).get("features"))
        if rest.startswith("bracket.") or rest.startswith("wing."):
            key = rest.split(".", 1)[1]
            feats = (spec.geometry_spec or {}).get("features") or []
            if not feats:
                return False
            f0 = feats[0]
            return key in f0 and f0[key] not in (None, "")
        return _get_nested(spec.geometry_spec or {}, rest) is not None
    if field.startswith("manufacturing."):
        return _get_nested(spec.manufacturing, field.split(".", 1)[1]) is not None
    if field.startswith("loads."):
        return _get_nested(spec.loads, field.split(".", 1)[1]) is not None
    if field == "constraints.max_stress_mpa":
        return any(c.metric in ("max_stress_mpa", "stress_mpa") for c in spec.constraints)
    if field.startswith("fluid."):
        return _get_nested(spec.fluid, field.split(".", 1)[1]) is not None
    if field == "optimization.goal":
        return bool(spec.objectives)
    return False


def build_clarification(spec: JobSpec) -> list[ClarificationQuestion]:
    """Ordered executor questionnaire — only unanswered fields."""
    candidates = _all_questions(spec)
    return [q for q in candidates if not field_is_set(spec, q.field)]


def _all_questions(spec: JobSpec) -> list[ClarificationQuestion]:
    q: list[ClarificationQuestion] = []
    seen: set[str] = set()

    def add(field: str, question: str) -> None:
        if field in seen:
            return
        seen.add(field)
        q.append(ClarificationQuestion(field=field, question=question))

    add(
        "deliverable_scope",
        "What should we deliver? **addon only** (part file only — e.g. wing/bracket), "
        "**full assembly** (part + your body STL), or **body only**.",
    )
    if not (spec.geometry_spec or {}).get("sculpt_method"):
        add(
            "geometry_spec.sculpt_method",
            "Which sculpt method? Call MCP `list_sculpt_methods` — e.g. **wing_loft**, **hull_loft**, "
            "**nozzle_axisymmetric**, **sdf_compose**, **bracket_parametric**, **mesh_displacement**.",
        )

    cat = spec.part_category.value if spec.part_category != PartCategory.CUSTOM else ""
    t = spec.user_request.lower()
    feats = (spec.geometry_spec or {}).get("features") or []

    if not feats:
        if cat == "bracket" or "bracket" in t:
            add("geometry_spec.bracket.style", "Bracket style? **L**, **T**, or describe the joint.")
            add("geometry_spec.bracket.leg_a_mm", "Leg A length (mm)?")
            add("geometry_spec.bracket.leg_b_mm", "Leg B length (mm)?")
            add("geometry_spec.bracket.thickness_mm", "Thickness (mm)?")
            add("geometry_spec.bracket.bend_angle_deg", "Bend angle (degrees)?")
            add(
                "geometry_spec.bracket.join_pattern",
                "Join pattern? **gusseted**, **filleted**, **organic_blend**, **butt**, **lap**.",
            )
        elif cat == "wing" or "wing" in t:
            add("geometry_spec.wing.span_mm", "Span (mm)?")
            add("geometry_spec.wing.chord_mm", "Chord (mm)?")
            add("geometry_spec.wing.angle_of_attack_deg", "Angle of attack (deg)?")
            add("geometry_spec.wing.profile", "Airfoil (e.g. **naca2412**)?")
        else:
            add(
                "geometry_spec.description",
                "Describe the part: size (mm), angles, holes, organic blends, and tolerance-critical faces.",
            )

    add("manufacturing.material", "Material for fabrication/order?")
    add("manufacturing.tolerance_mm", "Machining tolerance target (mm)?")
    add("manufacturing.machining_notes", "Machining notes (datums, hole pattern reference face, etc.)?")

    if spec.discipline == Discipline.FEA:
        add("loads.force_n", "Load in N and direction?")
        add("constraints.max_stress_mpa", "Max allowable stress (MPa)?")
        add("loads.constraint_hint", "How is the part constrained?")

    if spec.discipline == Discipline.CFD:
        add("fluid.speed_mph", "Design speed (mph)?")
        if "downforce" in t:
            add("fluid.target_downforce_lbs", "Target downforce (lbs) at that speed?")
        add("fluid.elevation", "**sea level** or altitude?")

    if spec.mode.value == "optimize" and not spec.objectives:
        add("optimization.goal", "Optimization goal? (min mass, min drag, hit downforce, etc.)")

    add("notify_email", "Email for REPORT + STL?")
    return q
