from __future__ import annotations

import json
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

from openclaw_engineering.config import get_settings
from openclaw_engineering.models import JobSpec

mcp = FastMCP("openclaw_engineering")


def _api() -> str:
    return get_settings().api_base


@mcp.tool()
def openclaw_engineering_submit_job(spec_json: str, user_request: str = "") -> str:
    """Submit a CAE job. spec_json is a JobSpec JSON object."""
    spec = JobSpec.model_validate(json.loads(spec_json))
    body = {"user_request": user_request or spec.user_request, "spec_json": spec.model_dump()}
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(f"{_api()}/jobs/json", json=body)
        resp.raise_for_status()
    return json.dumps(resp.json())


@mcp.tool()
def openclaw_engineering_job_status(job_id: str) -> str:
    """Get job status and metrics."""
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(f"{_api()}/jobs/{job_id}")
        resp.raise_for_status()
    return json.dumps(resp.json(), indent=2)


@mcp.tool()
def openclaw_engineering_list_artifacts(job_id: str) -> str:
    """List artifact filenames for a job."""
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(f"{_api()}/jobs/{job_id}")
        resp.raise_for_status()
    data = resp.json()
    return json.dumps(data.get("artifacts", []))


@mcp.tool()
def openclaw_engineering_fetch_artifact(job_id: str, name: str) -> str:
    """Return local API path to download an artifact (REPORT.md, result.stl, metrics.json)."""
    return f"{_api()}/jobs/{job_id}/artifacts/{name}"


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
