from __future__ import annotations

import json
import re
from typing import Any

import httpx

from openclaw_engineering.config import get_settings
from openclaw_engineering.feedback import build_agent_feedback
from openclaw_engineering.models import AgentFeedback, JobSpec, JobState, PassRecord

AGENT_SYSTEM = """You are a CAE optimization reviewer. Given reduced FEA/CFD metrics JSON,
respond with ONLY JSON:
{
  "recommendation": "short engineering note",
  "suggest_stop": false,
  "param_adjustments": {"param_name": value}
}
Use suggest_stop=true when further optimization is unlikely to help (diminishing returns).
For rear-wing CFD: tune angle_of_attack_deg, chord_mm, span_mm to hit downforce target at given speed.
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
                        "user_request": spec.user_request,
                        "objectives": [o.model_dump() for o in spec.objectives],
                        "constraints": [c.model_dump() for c in spec.constraints],
                        "fluid": spec.fluid,
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
