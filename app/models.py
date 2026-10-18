from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

RATING_VALUES = {"comfortable", "review", "new", "unsure"}


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

    # Source-linked discovery metadata, distinct from typed preparation requirements.
    discovery: dict[str, Any] = Field(default_factory=dict)


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


class TopicInfo(BaseModel):
    """A reviewed learning topic reached from a selected target's sourced facts."""

    key: str
    title: str = ""
    family: str = ""
    prerequisites: list[str] = Field(default_factory=list)
    resources: list[dict[str, str]] = Field(default_factory=list)
    required_by: dict[str, list[str]] = Field(default_factory=dict)


class GraphContext(BaseModel):
    opportunities: list[Opportunity] = Field(default_factory=list)
    tasks: list[PreparationTask] = Field(default_factory=list)
    evidence: list[EvidencePath] = Field(default_factory=list)
    fact_versions: dict[str, str] = Field(default_factory=dict)
    topics: list[TopicInfo] = Field(default_factory=list)


class RoadmapTopic(BaseModel):
    """One ordered roadmap entry; ratings and progress are self-reported."""

    key: str
    title: str
    family: str = ""
    order: int = 0
    rating: str = ""
    start_here: bool = False
    prerequisites: list[str] = Field(default_factory=list)
    resources: list[dict[str, str]] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)
    task_status: str = ""
    required_by: dict[str, list[str]] = Field(default_factory=dict)
    scheduled: bool = False
    note: str = ""
    basis: Literal["source_linked", "recommended"] = "source_linked"
    learn: list[str] = Field(default_factory=list)
    practice: str = ""
    done_when: str = ""
    hours_low: float = 0
    hours_high: float = 0
    week_allocations: dict[str, float] = Field(default_factory=dict)


class ProfileState(BaseModel):
    id: str = "unassigned"
    synthetic: bool = False
    country: str | None = Field(default=None, max_length=100)
    degree: str | None = Field(default=None, max_length=100)
    field: str | None = Field(default=None, max_length=100)
    year: int | None = Field(default=None, ge=1, le=20)
    total_years: int | None = Field(default=None, ge=1, le=20)
    institution_type: str | None = Field(default=None, max_length=100)
    institution_listed: bool | None = None
    right_to_work_singapore: bool | None = None
    weekly_hours: float = Field(default=6, ge=0, le=80)
    start_date: str = Field(default_factory=lambda: datetime.now(timezone(timedelta(hours=5, minutes=30))).date().isoformat())
    horizon_weeks: int = Field(default=8, ge=1, le=52)
    exam_weeks: list[str] = Field(default_factory=list)
    holidays: list[str] = Field(default_factory=list)
    weekly_pattern: dict[str, float] = Field(default_factory=dict)
    skill_ratings: dict[str, str] = Field(default_factory=dict)
    completed_task_ids: list[str] = Field(default_factory=list)
    received_events: list[str] = Field(default_factory=list)
    skills: dict[str, str] = Field(default_factory=dict)
    # Historical API callers retain their source-only contract. The study editor
    # explicitly requests auto or a chosen track for new topic-first proposals.
    study_track: Literal["auto", "software", "data", "research", "general", "source_only"] = "source_only"

    @field_validator("weekly_pattern", mode="before")
    @classmethod
    def _valid_pattern(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return {}
        pruned: dict[str, float] = {}
        for key, item in value.items():
            key = str(key)
            if key not in {"0", "1", "2", "3", "4", "5", "6"}:
                continue
            try:
                number = float(item)
            except (TypeError, ValueError):
                continue
            if 0 <= number <= 24:
                pruned[key] = number
        return pruned

    @field_validator("skill_ratings", mode="before")
    @classmethod
    def _valid_ratings(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return {}
        return {
            str(key)[:60]: item for key, item in value.items()
            if isinstance(item, str) and item in RATING_VALUES
        }


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
    roadmap: list[RoadmapTopic] = Field(default_factory=list)
    study_track: str = "source_only"
    study_track_reason: str = ""
    study_hours_low: float = 0
    study_hours_high: float = 0
    application_hours_low: float = 0
    application_hours_high: float = 0
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
