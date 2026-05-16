from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from nemoclaw.config import get_settings
from nemoclaw.models import JobSpec, JobState, JobStatus


def new_job_id() -> str:
    return uuid.uuid4().hex[:12]


def job_dir(job_id: str) -> Path:
    d = get_settings().jobs_dir / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_state(state: JobState) -> None:
    d = job_dir(state.job_id)
    (d / "state.json").write_text(state.model_dump_json(indent=2))
    (d / "spec.json").write_text(state.spec.model_dump_json(indent=2))


def load_state(job_id: str) -> JobState | None:
    p = get_settings().jobs_dir / job_id / "state.json"
    if not p.exists():
        return None
    return JobState.model_validate_json(p.read_text())


def create_job(spec: JobSpec) -> JobState:
    job_id = new_job_id()
    d = job_dir(job_id)
    (d / "work").mkdir(exist_ok=True)
    (d / "artifacts").mkdir(exist_ok=True)
    state = JobState(job_id=job_id, spec=spec, status=JobStatus.PENDING)
    save_state(state)
    return state


def artifact_path(job_id: str, name: str) -> Path:
    return get_settings().jobs_dir / job_id / "artifacts" / name


def list_artifacts(job_id: str) -> list[str]:
    ad = get_settings().jobs_dir / job_id / "artifacts"
    if not ad.exists():
        return []
    return sorted(p.name for p in ad.iterdir() if p.is_file())


def copy_input_stl(job_id: str, src: Path) -> Path:
    dest = job_dir(job_id) / "input.stl"
    shutil.copy2(src, dest)
    return dest


def write_flow_snapshot(job_id: str, flow: dict) -> None:
    p = job_dir(job_id) / "flow.snapshot.json"
    p.write_text(json.dumps(flow, indent=2))


def is_cancelled(job_id: str) -> bool:
    flag = get_settings().jobs_dir / job_id / "cancel.flag"
    return flag.exists()


def request_cancel(job_id: str) -> None:
    (get_settings().jobs_dir / job_id / "cancel.flag").touch()
