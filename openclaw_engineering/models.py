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


class CadBackend(str, Enum):
    BUILD123D = "build123d"
    CADQUERY = "cadquery"
    FREECAD = "freecad"
    STL_DEFORM = "stl_deform"


class GeometryKind(str, Enum):
    REAR_WING = "rear_wing"
    DOWNFORCE_KIT = "downforce_kit"


class JobStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    AWAITING_USER = "awaiting_user"
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
    sense: str = "minimize"


class Constraint(BaseModel):
    metric: str
    op: str  # le | ge | eq
    value: float
    unit: str = ""


class OnShapeRef(BaseModel):
    document_id: str
    workspace_id: str
    element_id: str
    part_name: str | None = None


class ClarificationQuestion(BaseModel):
    field: str
    question: str


class JobSpec(BaseModel):
    mode: JobMode = JobMode.OPTIMIZE
    discipline: Discipline = Discipline.FEA
    cad_backend: CadBackend = CadBackend.BUILD123D
    user_request: str = ""
    objectives: list[Objective] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    loads: dict[str, Any] = Field(default_factory=dict)
    boundary_conditions: dict[str, Any] = Field(default_factory=dict)
    fluid: dict[str, Any] = Field(default_factory=dict)
    design_params: list[DesignParam] = Field(default_factory=list)
    cad_params: dict[str, Any] = Field(default_factory=dict)
    geometry_kind: GeometryKind = GeometryKind.REAR_WING
    grabcad_query: str | None = None
    reference_stl: str | None = None
    run_speed_sweep: bool = True
    run_wing_fea: bool = True
    input_stl: str | None = None
    mesh_size: float | None = None
    max_passes: int | None = None
    flow_template: str = "optimize_fea.yaml"
    session_id: str | None = None
    onshape: OnShapeRef | None = None
    notify_email: str | None = None
    needs_clarification: list[ClarificationQuestion] = Field(default_factory=list)
    use_optuna: bool = False
    agent_review_each_pass: bool = True

    def default_objective_metric(self) -> str:
        if self.objectives:
            return self.objectives[0].metric
        if self.discipline == Discipline.CFD:
            return "cd"
        return "mass_kg"


class SpeedSweepRow(BaseModel):
    speed_mph: float
    cd: float | None = None
    cl: float | None = None
    downforce_lbs: float | None = None
    drag_lbs: float | None = None


class PassRecord(BaseModel):
    pass_index: int
    params: dict[str, float]
    metrics: dict[str, float]
    feasible: bool
    objective_value: float
    relative_gain: float | None = None
    agent_note: str | None = None


class AgentFeedback(BaseModel):
    """Reduced CAE feedback returned to Nemotron between passes."""
    pass_index: int
    metrics: dict[str, float]
    feasible: bool
    constraint_violations: list[str] = Field(default_factory=list)
    recommendation: str = ""
    suggest_stop: bool = False
    param_adjustments: dict[str, float] = Field(default_factory=dict)


class JobState(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.PENDING
    spec: JobSpec
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    stage: str = "queued"
    message: str = ""
    passes: list[PassRecord] = Field(default_factory=list)
    agent_log: list[AgentFeedback] = Field(default_factory=list)
    speed_sweep: list[SpeedSweepRow] = Field(default_factory=list)
    wing_fea: dict[str, Any] = Field(default_factory=dict)
    vmax_estimated_mph: float | None = None
    stop_reason: str | None = None
    best_params: dict[str, float] = Field(default_factory=dict)
    error: str | None = None
    pending_questions: list[ClarificationQuestion] = Field(default_factory=list)

    def touch(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)
        self.updated_at = datetime.now(timezone.utc)


class JobSubmitRequest(BaseModel):
    user_request: str
    spec_json: dict[str, Any] | None = None
    input_stl_path: str | None = None
    session_id: str | None = None
    notify_email: str | None = None


class JobSubmitResponse(BaseModel):
    job_id: str
    status: JobStatus
    questions: list[ClarificationQuestion] = Field(default_factory=list)


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    stage: str
    message: str
    passes: list[PassRecord]
    stop_reason: str | None = None
    artifacts: list[str] = Field(default_factory=list)
    pending_questions: list[ClarificationQuestion] = Field(default_factory=list)
