from __future__ import annotations

"""
Planning is owned by the OpenClaw agent (Nemotron).
This module only validates/normalizes JobSpec when the agent submits JSON via MCP.
"""

import json
import re
from typing import Any

from openclaw_engineering.constraints import enforce_agent_rules, infer_missing_from_request
from openclaw_engineering.models import Discipline, JobSpec


def normalize_spec(spec: JobSpec, user_request: str = "", input_stl: str | None = None) -> JobSpec:
    """Apply safety rules the agent should have set — fill gaps only when obvious."""
    spec.user_request = user_request or spec.user_request
    spec.input_stl = input_stl or spec.input_stl
    spec = infer_missing_from_request(spec)
    spec = enforce_agent_rules(spec)
    if spec.discipline == Discipline.FEA and not spec.loads.get("yield_strength_mpa"):
        for c in spec.constraints:
            if c.metric == "max_stress_mpa":
                spec.loads.setdefault("yield_strength_mpa", c.value * 1.1)
                break
    return spec


def parse_spec_json(spec_json: str | dict) -> JobSpec:
    if isinstance(spec_json, str):
        data = json.loads(spec_json)
    else:
        data = spec_json
    return JobSpec.model_validate(data)


def plan_job_sync(user_request: str, input_stl: str | None = None) -> JobSpec:
    """
    Fallback when no agent spec (CLI/dry-run only).
    OpenClaw demos should always pass full JobSpec via MCP.
    """
    spec = infer_missing_from_request(
        JobSpec(user_request=user_request, input_stl=input_stl)
    )
    return enforce_agent_rules(spec)
