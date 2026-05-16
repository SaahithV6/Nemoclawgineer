from __future__ import annotations

import json
import re
from typing import Any

import httpx

from nemoclaw.config import get_settings, load_defaults
from nemoclaw.models import (
    Constraint,
    DesignParam,
    Discipline,
    JobMode,
    JobSpec,
    Objective,
)


PLANNER_SYSTEM = """You are a CAE job planner. Output ONLY valid JSON matching JobSpec fields:
mode (optimize|analyze|generate|collab), discipline (fea|cfd), objectives[], constraints[],
loads{}, fluid{}, design_params[{name,min,max,initial,unit}], flow_template, mesh_size, max_passes.
Use flow_template optimize_fea.yaml for structural optimization, analyze_cfd.yaml for CFD analysis.
"""


def _heuristic_plan(user_request: str, input_stl: str | None) -> JobSpec:
    text = user_request.lower()
    discipline = Discipline.CFD if any(k in text for k in ("drag", "lift", "cfd", "flow", "reynolds", "cd", "cl")) else Discipline.FEA
    mode = JobMode.ANALYZE if "analyze" in text or "report" in text and "optim" not in text else JobMode.OPTIMIZE
    if not input_stl and any(k in text for k in ("create", "generate", "design")):
        mode = JobMode.GENERATE

    objectives = [Objective(metric="cd", sense="minimize")] if discipline == Discipline.CFD else [Objective(metric="mass_kg", sense="minimize")]
    constraints: list[Constraint] = []
    m = re.search(r"(\d+(?:\.\d+)?)\s*mpa", text)
    if m:
        constraints.append(Constraint(metric="max_stress_mpa", op="le", value=float(m.group(1)), unit="MPa"))
    m = re.search(r"(\d+(?:\.\d+)?)\s*n", text)
    force = float(m.group(1)) if m else 500.0

    design_params = [
        DesignParam(name="thickness_mm", min=2.0, max=12.0, initial=6.0, unit="mm"),
    ]
    flow = "analyze_cfd.yaml" if discipline == Discipline.CFD and mode == JobMode.ANALYZE else "optimize_fea.yaml"
    if discipline == Discipline.CFD:
        flow = "analyze_cfd.yaml"

    return JobSpec(
        mode=mode,
        discipline=discipline,
        user_request=user_request,
        objectives=objectives,
        constraints=constraints,
        loads={"force_n": force},
        fluid={"velocity_ms": 15.0, "density": 1.2},
        design_params=design_params if mode == JobMode.OPTIMIZE else [],
        input_stl=input_stl,
        flow_template=flow,
    )


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("{"):
        return json.loads(text)
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise ValueError("No JSON in planner response")
    return json.loads(m.group(0))


async def plan_job(user_request: str, input_stl: str | None = None) -> JobSpec:
    settings = get_settings()
    if not settings.openclaw_api_token:
        spec = _heuristic_plan(user_request, input_stl)
        spec.input_stl = input_stl
        return spec

    url = settings.openclaw_gateway_url.rstrip("/") + "/v1/chat/completions"
    payload = {
        "model": settings.openclaw_model,
        "messages": [
            {"role": "system", "content": PLANNER_SYSTEM},
            {"role": "user", "content": user_request},
        ],
        "temperature": 0,
    }
    headers = {"Authorization": f"Bearer {settings.openclaw_api_token}"}
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = _extract_json(content)
        spec = JobSpec.model_validate(parsed)
        spec.user_request = user_request
        spec.input_stl = input_stl or spec.input_stl
        return spec
    except Exception:
        spec = _heuristic_plan(user_request, input_stl)
        spec.input_stl = input_stl
        return spec


def plan_job_sync(user_request: str, input_stl: str | None = None) -> JobSpec:
    import asyncio

    return asyncio.run(plan_job(user_request, input_stl))
