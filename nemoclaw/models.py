from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobMode(str, Enum):
    OPTIMIZE = "optimize"
    ANALYZE = "analyze"
    GENERATE = "generate"
    COLLAB = "collab"


class Discipline(str, Enum):
    FEA = "fea"
    CFD = "cfd"


class JobStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DesignParam(BaseModel):
    name: str
    min: float
    max: float
    initial: float
    unit: str = "mm"


class Objective(BaseModel):
    metric: str
    sense: str = "minimize"  # minimize | maximize


class Constraint(BaseModel):
    metric: str
    op: str  # le | ge | eq
    value: float
    unit: str = ""


class JobSpec(BaseModel):
    mode: JobMode = JobMode.OPTIMIZE
    discipline: Discipline = Discipline.FEA
    user_request: str = ""
    objectives: list[Objective] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    loads: dict[str, Any] = Field(default_factory=dict)
    boundary_conditions: dict[str, Any] = Field(default_factory=dict)
    fluid: dict[str, Any] = Field(default_factory=dict)
    design_params: list[DesignParam] = Field(default_factory=list)
    input_stl: str | None = None
    mesh_size: float | None = None
    max_passes: int | None = None
    flow_template: str = "optimize_fea.yaml"
    session_id: str | None = None

    def default_objective_metric(self) -> str:
        if self.objectives:
            return self.objectives[0].metric
        if self.discipline == Discipline.CFD:
            return "cd"
        return "mass_kg"


class PassRecord(BaseModel):
    pass_index: int
    params: dict[str, float]
    metrics: dict[str, float]
    feasible: bool
    objective_value: float
    relative_gain: float | None = None


class JobState(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.PENDING
    spec: JobSpec
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    stage: str = "queued"
    message: str = ""
    passes: list[PassRecord] = Field(default_factory=list)
    stop_reason: str | None = None
    best_params: dict[str, float] = Field(default_factory=dict)
    error: str | None = None

    def touch(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)
        self.updated_at = datetime.now(timezone.utc)


class JobSubmitRequest(BaseModel):
    user_request: str
    spec_json: dict[str, Any] | None = None
    input_stl_path: str | None = None
    session_id: str | None = None


class JobSubmitResponse(BaseModel):
    job_id: str
    status: JobStatus


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    stage: str
    message: str
    passes: list[PassRecord]
    stop_reason: str | None = None
    artifacts: list[str] = Field(default_factory=list)
