from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from openclaw_engineering.config import get_settings
from openclaw_engineering.conversation import get_conversation_store
from openclaw_engineering.models import (
    JobSpec,
    JobStatus,
    JobStatusResponse,
    JobSubmitRequest,
    JobSubmitResponse,
)
from openclaw_engineering.orchestrator import get_job, resume_job_after_clarification, submit_job
from openclaw_engineering.store import artifact_path, list_artifacts, request_cancel, save_state

app = FastAPI(title="OpenClaw Engineering API", version="0.2.0")


class AnswerBody(BaseModel):
    field: str
    answer: str


def _job_response(state) -> JobSubmitResponse:
    return JobSubmitResponse(
        job_id=state.job_id,
        status=state.status,
        questions=state.pending_questions or state.spec.needs_clarification,
    )


@app.get("/health")
def health():
    return {"status": "ok", "dry_run": get_settings().openclaw_engineering_dry_run}


@app.post("/jobs", response_model=JobSubmitResponse)
async def create_job_endpoint(
    user_request: str = Form(...),
    spec_json: str | None = Form(None),
    session_id: str | None = Form(None),
    notify_email: str | None = Form(None),
    discord_user_id: str | None = Form(None),
    file: UploadFile | None = File(None),
):
    spec = JobSpec.model_validate_json(spec_json) if spec_json else None
    stl_path = None
    if file and file.filename:
        tmp = get_settings().data_dir / "uploads"
        tmp.mkdir(parents=True, exist_ok=True)
        stl_path = tmp / file.filename
        with stl_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)
    state = submit_job(
        user_request,
        spec=spec,
        input_stl=stl_path,
        session_id=session_id,
        notify_email=notify_email,
        discord_user_id=discord_user_id,
    )
    if state.status == JobStatus.AWAITING_USER and session_id:
        get_conversation_store().set_pending(session_id, state.spec, state.pending_questions)
    return _job_response(state)


@app.post("/jobs/json", response_model=JobSubmitResponse)
def create_job_json(body: JobSubmitRequest):
    spec = JobSpec.model_validate(body.spec_json) if body.spec_json else None
    stl = Path(body.input_stl_path) if body.input_stl_path else None
    state = submit_job(
        body.user_request,
        spec=spec,
        input_stl=stl,
        session_id=body.session_id,
        notify_email=body.notify_email,
        discord_user_id=body.discord_user_id,
    )
    return _job_response(state)


@app.post("/jobs/{job_id}/answer", response_model=JobSubmitResponse)
def answer_clarification(job_id: str, body: AnswerBody):
    state = get_job(job_id)
    if not state:
        raise HTTPException(404, "Job not found")
    if state.status != JobStatus.AWAITING_USER:
        raise HTTPException(400, "Job is not awaiting clarification")

    store = get_conversation_store()
    sid = state.spec.session_id or job_id
    spec = store.merge_answer(sid, body.field, body.answer)
    if spec is None:
        state = get_job(job_id)
        return _job_response(state)

    state.spec = spec
    state.spec.needs_clarification = []
    save_state(state)
    resume_job_after_clarification(state)
    return _job_response(state)


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
        pending_questions=state.pending_questions,
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
    uvicorn.run(app, host=s.openclaw_engineering_api_host, port=s.openclaw_engineering_api_port, log_level="info")


if __name__ == "__main__":
    run_server()
