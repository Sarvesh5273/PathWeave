from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Fact(BaseModel):
    name: str
    value: Any = None
    status: Literal["known", "unknown", "conflicting"] = "unknown"
    kind: Literal["requirement", "preference", "information"] = "information"
    excerpt: str = ""
    source_url: str = ""
    source_id: str = ""
    version_id: str = ""
    simulated: bool = False


class SourceSnapshot(BaseModel):
    id: str
    url: str
    title: str = ""
    text: str = ""
    checked_at: str = Field(default_factory=utc_now)
    content_hash: str = ""
    mode: Literal["live", "cached", "synthetic"] = "live"


class Opportunity(BaseModel):
    id: str
    program: str
    cycle: str = "unknown"
    category: Literal["Research", "Company"] = "Research"
    country: str = "Unknown"
    source_url: str
    checked_at: str = Field(default_factory=utc_now)
    call_status: Literal["open", "closed", "future", "unknown"] = "unknown"
    verification: Literal["verified", "partial", "uncertain"] = "partial"
    mode: Literal["live", "cached", "synthetic"] = "live"
    facts: list[Fact] = Field(default_factory=list)
    summary: str = ""


class EvidencePath(BaseModel):
    target_id: str = ""
    task_id: str = ""
    nodes: list[str] = Field(default_factory=list)
    relationship: str = ""
    source_url: str = ""
    excerpt: str = ""


class PreparationTask(BaseModel):
    id: str
    title: str
    category: Literal["Shared", "Research", "Company"] = "Shared"
    hours_low: float = 0
    hours_high: float = 0
    dependencies: list[str] = Field(default_factory=list)
    target_ids: list[str] = Field(default_factory=list)
    fact_names: list[str] = Field(default_factory=list)
    waiting_for: str | None = None
    artifact_type: str = ""
    provenance: str = "planner_estimate"
    due_at: str | None = None


class GraphContext(BaseModel):
    opportunities: list[Opportunity] = Field(default_factory=list)
    tasks: list[PreparationTask] = Field(default_factory=list)
    evidence: list[EvidencePath] = Field(default_factory=list)
    fact_versions: dict[str, str] = Field(default_factory=dict)


class ProfileState(BaseModel):
    id: str = "demo-student"
    synthetic: bool = True
    country: str | None = "India"
    degree: str | None = "BTech"
    field: str | None = "computer_science"
    year: int | None = 3
    total_years: int | None = 4
    institution_type: str | None = "non_iit"
    institution_listed: bool | None = None
    right_to_work_singapore: bool | None = None
    weekly_hours: float = Field(default=6, ge=0, le=80)
    start_date: str = "2026-10-19"
    horizon_weeks: int = Field(default=8, ge=1, le=52)
    exam_weeks: list[str] = Field(default_factory=lambda: ["2026-11-02"])
    completed_task_ids: list[str] = Field(default_factory=list)
    received_events: list[str] = Field(default_factory=list)
    skills: dict[str, str] = Field(default_factory=lambda: {"python": "self_reported", "research": "not_assessed"})


class CriterionResult(BaseModel):
    name: str
    status: Literal["met", "not_met", "unknown", "preference", "information"]
    explanation: str
    fact_version_id: str = ""
    source_url: str = ""
    excerpt: str = ""


class TargetAssessment(BaseModel):
    target_id: str
    eligibility: Literal["conditions_met", "not_eligible", "needs_review"] = "needs_review"
    call_status: str = "unknown"
    readiness: str = "not_assessed"
    schedule_status: Literal["feasible", "at_risk", "infeasible", "cannot_certify", "excluded"] = "cannot_certify"
    reasons: list[str] = Field(default_factory=list)
    criteria: list[CriterionResult] = Field(default_factory=list)
    required_task_ids: list[str] = Field(default_factory=list)
    used_fact_versions: list[str] = Field(default_factory=list)


class PlanTask(BaseModel):
    task_id: str
    title: str
    category: str
    target_ids: list[str] = Field(default_factory=list)
    status: Literal["scheduled", "completed", "waiting", "blocked", "unscheduled"] = "unscheduled"
    hours_low: float = 0
    hours_high: float = 0
    week_allocations: dict[str, float] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    waiting_for: str | None = None
    reason: str = ""
    fact_version_ids: list[str] = Field(default_factory=list)


class Plan(BaseModel):
    id: str
    created_at: str = Field(default_factory=utc_now)
    selected_ids: list[str]
    profile: ProfileState
    targets: list[TargetAssessment]
    tasks: list[PlanTask]
    evidence: list[EvidencePath] = Field(default_factory=list)
    fact_versions: dict[str, str] = Field(default_factory=dict)
    total_hours_low: float = 0
    total_hours_high: float = 0
    available_hours: float = 0
    weekly_used: dict[str, float] = Field(default_factory=dict)
    status: Literal["proposed", "accepted", "stale", "superseded"] = "proposed"
    next_action: str = ""
    warnings: list[str] = Field(default_factory=list)
    affected_target_ids: list[str] = Field(default_factory=list)
    affected_task_ids: list[str] = Field(default_factory=list)


class FactChange(BaseModel):
    opportunity_id: str
    fact_name: str
    old_version_id: str = ""
    new_version_id: str = ""
    old_value: Any = None
    new_value: Any = None


class ChangeImpact(BaseModel):
    changes: list[FactChange] = Field(default_factory=list)
    affected_plan_ids: list[str] = Field(default_factory=list)
    affected_target_ids: list[str] = Field(default_factory=list)
    affected_task_ids: list[str] = Field(default_factory=list)
    paths: list[EvidencePath] = Field(default_factory=list)
    semantic_change: bool = False
    preserved_task_ids: list[str] = Field(default_factory=list)


class SourceOutcome(BaseModel):
    url: str
    status: Literal["success", "partial", "failed"] = "success"
    opportunity_ids: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class DiscoveryResult(BaseModel):
    query: str
    opportunities: list[Opportunity] = Field(default_factory=list)
    snapshots: list[SourceSnapshot] = Field(default_factory=list)
    source_outcomes: list[SourceOutcome] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    provider: str = "TinyFish"
    mode: str = "live"


class ToolTrace(BaseModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = 0
    result_summary: str = ""
    mode: str = "live"
    outcome: Literal["executed", "rejected", "failed"] = "executed"

