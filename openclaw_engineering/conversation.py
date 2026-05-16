from __future__ import annotations

import json
from pathlib import Path

from openclaw_engineering.config import get_settings
from openclaw_engineering.models import ClarificationQuestion, Constraint, JobSpec


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
        self._apply_answer(spec, field, answer)
        remaining = [q for q in questions if q.field != field]
        if remaining:
            self.set_pending(session_id, spec, remaining)
            return None
        self.clear(session_id)
        return spec

    def _apply_answer(self, spec: JobSpec, field: str, answer: str) -> None:
        text = answer.strip().lower()
        if field == "target_speed_mph":
            spec.fluid["speed_mph"] = float(answer.split()[0])
            spec.fluid["velocity_ms"] = float(answer.split()[0]) * 0.44704
        elif field == "target_downforce_lbs":
            spec.fluid["target_downforce_lbs"] = float(answer.split()[0])
            spec.constraints.append(
                Constraint(
                    metric="downforce_n",
                    op="ge",
                    value=float(answer.split()[0]) * 4.44822,
                    unit="N",
                )
            )
        elif field == "elevation":
            spec.fluid["elevation"] = "sea_level" if "sea" in text else answer
            if "sea" in text:
                spec.fluid["density"] = 1.225
        elif field == "notify_email":
            spec.notify_email = answer.strip()
        elif field in spec.cad_params or field.endswith("_mm") or field.endswith("_deg"):
            try:
                spec.cad_params[field] = float(answer.split()[0])
            except ValueError:
                spec.cad_params[field] = answer
        else:
            spec.cad_params[field] = answer


_store: ConversationStore | None = None


def get_conversation_store() -> ConversationStore:
    global _store
    if _store is None:
        _store = ConversationStore()
    return _store
