from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openclaw_engineering.config import get_settings
from openclaw_engineering.models import ClarificationQuestion, Constraint, JobSpec, PartCategory


class ConversationStore:
    def __init__(self):
        self.path = get_settings().data_dir / "sessions.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, dict] = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text())
        return {}

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2))

    def set_pending(self, session_id: str, spec: JobSpec, questions: list[ClarificationQuestion]) -> None:
        self._data[session_id] = {
            "spec": spec.model_dump(),
            "questions": [q.model_dump() for q in questions],
        }
        self._save()

    def get_pending(self, session_id: str) -> tuple[JobSpec | None, list[ClarificationQuestion]]:
        entry = self._data.get(session_id)
        if not entry:
            return None, []
        return JobSpec.model_validate(entry["spec"]), [
            ClarificationQuestion.model_validate(q) for q in entry["questions"]
        ]

    def clear(self, session_id: str) -> None:
        self._data.pop(session_id, None)
        self._save()

    def merge_answer(self, session_id: str, field: str, answer: str) -> JobSpec | None:
        spec, questions = self.get_pending(session_id)
        if not spec:
            return None
        _apply_answer(spec, field, answer)
        remaining = [q for q in questions if q.field != field]
        if remaining:
            self.set_pending(session_id, spec, remaining)
            return None
        self.clear(session_id)
        spec.needs_clarification = []
        return spec


def _set_nested(data: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cur = data
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


def _apply_answer(spec: JobSpec, field: str, answer: str) -> None:
    text = answer.strip().lower()
    raw = answer.strip()

    if field == "deliverable_scope":
        if "full" in text or "assembly" in text or "body" in text and "only" not in text:
            from openclaw_engineering.models import DeliverableScope

            spec.deliverable_scope = DeliverableScope.FULL_ASSEMBLY
        elif "body only" in text:
            from openclaw_engineering.models import DeliverableScope

            spec.deliverable_scope = DeliverableScope.BODY_ONLY
        else:
            from openclaw_engineering.models import DeliverableScope

            spec.deliverable_scope = DeliverableScope.ADDON_ONLY
        return

    if field == "part_category":
        mapping = {
            "wing": PartCategory.WING,
            "bracket": PartCategory.BRACKET,
            "aero": PartCategory.AERO_KIT,
            "kit": PartCategory.AERO_KIT,
            "structural": PartCategory.STRUCTURAL,
        }
        for key, cat in mapping.items():
            if key in text:
                spec.part_category = cat
                break
        else:
            spec.part_category = PartCategory.CUSTOM
        from openclaw_engineering.tools.geometry_catalog import ensure_geometry_spec

        spec.geometry_spec = ensure_geometry_spec(
            spec.geometry_spec, spec.user_request, spec.part_category.value
        )
        return

    if field == "geometry_spec.sculpt_method":
        spec.geometry_spec["sculpt_method"] = raw.strip()
        return

    if field == "geometry_spec.description":
        spec.geometry_spec.setdefault("features", []).append(
            {"type": "custom_block", "notes": raw, "size_mm": [100, 80, 40]}
        )
        return

    if field.startswith("geometry_spec.bracket."):
        key = field.split(".")[-1]
        feats = spec.geometry_spec.setdefault("features", [])
        if not feats or feats[0].get("type") not in ("bracket", "gusset"):
            feats.insert(0, {"type": "bracket", "style": "L"})
        val: Any = raw
        if key.endswith("_mm") or key.endswith("_deg"):
            try:
                val = float(raw.split()[0])
            except ValueError:
                val = raw
        feats[0][key] = val
        return

    if field.startswith("geometry_spec.wing."):
        key = field.split(".")[-1]
        feats = spec.geometry_spec.setdefault("features", [])
        if not feats or feats[0].get("type") != "wing":
            feats.insert(0, {"type": "wing", "profile": "naca2412"})
        val = raw
        if key.endswith("_mm") or key.endswith("_deg"):
            try:
                val = float(raw.split()[0])
            except ValueError:
                val = raw
        feats[0][key] = val
        return

    if field.startswith("manufacturing."):
        key = field.split(".", 1)[1]
        val: Any = raw
        if key == "tolerance_mm":
            val = float(raw.split()[0])
        spec.manufacturing[key] = val
        spec.geometry_spec.setdefault(key, val)
        return

    if field == "target_speed_mph" or field == "fluid.speed_mph":
        spec.fluid["speed_mph"] = float(raw.split()[0])
        spec.fluid["velocity_ms"] = float(raw.split()[0]) * 0.44704
    elif field == "target_downforce_lbs" or field == "fluid.target_downforce_lbs":
        spec.fluid["target_downforce_lbs"] = float(raw.split()[0])
        spec.constraints.append(
            Constraint(
                metric="downforce_n",
                op="ge",
                value=float(raw.split()[0]) * 4.44822,
                unit="N",
            )
        )
    elif field == "elevation" or field == "fluid.elevation":
        spec.fluid["elevation"] = "sea_level" if "sea" in text else raw
        if "sea" in text:
            spec.fluid["density"] = 1.225
    elif field == "loads.force_n":
        try:
            spec.loads["force_n"] = float(raw.split()[0])
        except ValueError:
            spec.loads["force_description"] = raw
    elif field == "loads.constraint_hint":
        spec.loads["constraint_hint"] = raw
    elif field == "constraints.max_stress_mpa":
        spec.constraints.append(
            Constraint(metric="max_stress_mpa", op="le", value=float(raw.split()[0]), unit="MPa")
        )
    elif field == "optimization.goal":
        from openclaw_engineering.models import Objective

        if "mass" in text:
            spec.objectives.append(Objective(metric="mass_kg", sense="minimize"))
        elif "drag" in text or "cd" in text:
            spec.objectives.append(Objective(metric="cd", sense="minimize"))
        elif "downforce" in text:
            spec.objectives.append(Objective(metric="downforce_n", sense="maximize"))
    elif field == "notify_email":
        spec.notify_email = raw
    elif field.endswith("_mm") or field.endswith("_deg"):
        try:
            spec.cad_params[field] = float(raw.split()[0])
        except ValueError:
            spec.cad_params[field] = raw
    else:
        spec.cad_params[field] = raw


_store: ConversationStore | None = None


def get_conversation_store() -> ConversationStore:
    global _store
    if _store is None:
        _store = ConversationStore()
    return _store
