from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from nemoclaw.config import get_settings
from nemoclaw.models import (
    JobSpec,
    JobStatusResponse,
    JobSubmitRequest,
    JobSubmitResponse,
)
from nemoclaw.orchestrator import get_job, submit_job
from nemoclaw.store import artifact_path, list_artifacts, request_cancel

app = FastAPI(title="Nemoclaw API", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok", "dry_run": get_settings().nemoclaw_dry_run}


@app.post("/jobs", response_model=JobSubmitResponse)
async def create_job_endpoint(
    user_request: str = Form(...),
    spec_json: str | None = Form(None),
    session_id: str | None = Form(None),
    file: UploadFile | None = File(None),
):
    spec = None
    if spec_json:
        spec = JobSpec.model_validate_json(spec_json)
    stl_path = None
    if file and file.filename:
        tmp = get_settings().data_dir / "uploads"
        tmp.mkdir(parents=True, exist_ok=True)
        stl_path = tmp / file.filename
        with stl_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)
    state = submit_job(user_request, spec=spec, input_stl=stl_path, session_id=session_id)
    return JobSubmitResponse(job_id=state.job_id, status=state.status)


@app.post("/jobs/json", response_model=JobSubmitResponse)
def create_job_json(body: JobSubmitRequest):
    spec = JobSpec.model_validate(body.spec_json) if body.spec_json else None
    stl = Path(body.input_stl_path) if body.input_stl_path else None
    state = submit_job(body.user_request, spec=spec, input_stl=stl, session_id=body.session_id)
    return JobSubmitResponse(job_id=state.job_id, status=state.status)


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
def job_status(job_id: str):
    state = get_job(job_id)
    if not state:
        raise HTTPException(404, "Job not found")
    return JobStatusResponse(
        job_id=state.job_id,
        status=state.status,
        stage=state.stage,
        message=state.message,
        passes=state.passes,
        stop_reason=state.stop_reason,
        artifacts=list_artifacts(job_id),
    )


@app.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    if not get_job(job_id):
        raise HTTPException(404, "Job not found")
    request_cancel(job_id)
    return {"ok": True}


@app.get("/jobs/{job_id}/artifacts/{name}")
def fetch_artifact(job_id: str, name: str):
    path = artifact_path(job_id, name)
    if not path.exists():
        raise HTTPException(404, "Artifact not found")
    return FileResponse(path, filename=name)


def run_server():
    import uvicorn

    s = get_settings()
    uvicorn.run(app, host=s.nemoclaw_api_host, port=s.nemoclaw_api_port, log_level="info")


if __name__ == "__main__":
    run_server()
