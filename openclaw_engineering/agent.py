from __future__ import annotations

import json
import re
from typing import Any

import httpx

from openclaw_engineering.config import get_settings
from openclaw_engineering.feedback import build_agent_feedback
from openclaw_engineering.models import AgentFeedback, JobSpec, JobState, PassRecord

AGENT_SYSTEM = """You are the CAD/CAE tuning loop for OpenClaw Engineering on Brev.

After each simulation pass you receive REDUCED metrics (inputs/outputs only).
You tune the 3D CAD generator for the NEXT pass by returning param_adjustments.

Respond with ONLY JSON:
{
  "recommendation": "engineering note for the report",
  "suggest_stop": false,
  "param_adjustments": {"param_name": number}
}

Rules:
- CFD rear wing: adjust angle_of_attack_deg, chord_mm, span_mm, thickness_mm toward objectives/constraints.
- CFD downforce kit: adjust splitter_extension_mm, diffuser_angle_deg, etc.
- FEA: you should have set loads in JobSpec.loads before the job ran; use metrics to tune thickness_mm or thickness_scale.
- suggest_stop=true when gains are diminishing or constraints are met.
- Never request impossible geometry; stay within JobSpec design_params min/max.
"""


async def review_pass_async(
    spec: JobSpec,
    state: JobState,
    record: PassRecord,
) -> AgentFeedback:
    fb = build_agent_feedback(spec, record)
    settings = get_settings()
    if not spec.agent_review_each_pass or not settings.openclaw_api_token:
        return fb

    payload = {
        "model": settings.openclaw_model,
        "messages": [
            {"role": "system", "content": AGENT_SYSTEM},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "pass_index": record.pass_index,
                        "user_request": spec.user_request,
                        "discipline": spec.discipline.value,
                        "geometry_kind": spec.geometry_kind.value,
                        "objectives": [o.model_dump() for o in spec.objectives],
                        "constraints": [c.model_dump() for c in spec.constraints],
                        "fluid": spec.fluid,
                        "loads": spec.loads,
                        "boundary_conditions": spec.boundary_conditions,
                        "last_params": record.params,
                        "cad_params": spec.cad_params,
                        "feedback": fb.model_dump(),
                    }
                ),
            },
        ],
        "temperature": 0,
    }
    url = settings.openclaw_gateway_url.rstrip("/") + "/v1/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {settings.openclaw_api_token}"},
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"]
        parsed = _extract_json(text)
        fb.recommendation = parsed.get("recommendation", "")
        fb.suggest_stop = bool(parsed.get("suggest_stop", False))
        fb.param_adjustments = parsed.get("param_adjustments") or {}
    except Exception:
        pass
    return fb


def review_pass_sync(spec: JobSpec, state: JobState, record: PassRecord) -> AgentFeedback:
    import asyncio

    return asyncio.run(review_pass_async(spec, state, record))


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("{"):
        return json.loads(text)
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return {}
    return json.loads(m.group(0))
