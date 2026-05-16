from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

from openclaw_engineering.config import get_settings
from openclaw_engineering.models import JobSpec
from openclaw_engineering.integrations.picogk_runner import picogk_status
from openclaw_engineering.sculpt.engine import build_sculpt, list_sculpt_methods, sculpt_method_schema

mcp = FastMCP("openclaw_engineering")


def _api() -> str:
    return get_settings().api_base


@mcp.tool()
def openclaw_engineering_picogk_status() -> str:
    """Check whether optional LEAP71 PicoGK backend is installed and enabled on Brev."""
    return json.dumps(picogk_status(), indent=2)


@mcp.tool()
def openclaw_engineering_list_sculpt_methods() -> str:
    """
    List dynamic sculpt methods Nemotron can choose (wing loft, hull, nozzle, SDF, mesh deform, bracket).
    Use before filling geometry_spec — do not limit users to fixed part categories.
    """
    return json.dumps(list_sculpt_methods(), indent=2)


@mcp.tool()
def openclaw_engineering_sculpt_method_schema(method_id: str) -> str:
    """Return param_schema for a sculpt method (call after list_sculpt_methods)."""
    return json.dumps(sculpt_method_schema(method_id), indent=2)


@mcp.tool()
def openclaw_engineering_preview_sculpt(geometry_spec_json: str) -> str:
    """
    Quick STL preview from geometry_spec (sculpt_method + params) without full FEA/CFD job.
    Returns path hint and validation metadata.
    """
    spec = json.loads(geometry_spec_json)
    out = Path(tempfile.mkdtemp(prefix="openclaw-sculpt-")) / "preview.stl"
    build_sculpt(spec, spec.get("params", {}), out)
    return json.dumps(
        {
            "stl_path": str(out),
            "sculpt_method": spec.get("sculpt_method"),
            "bytes": out.stat().st_size if out.exists() else 0,
        },
        indent=2,
    )


@mcp.tool()
def openclaw_engineering_submit_job(spec_json: str, user_request: str = "") -> str:
    """Submit a CAE job. spec_json is a JobSpec JSON object with geometry_spec.sculpt_method."""
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
