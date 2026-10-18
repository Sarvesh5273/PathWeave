from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from pydantic.alias_generators import to_camel

from app.models import Fact, SourceSnapshot


SearchText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Seniority = Literal["internship", "new_grad", "entry_level", "experienced"]
OpportunityType = Literal["company_roles", "research_programs"]


class DiscoveryPreferences(BaseModel):
    """Scout's preference surface; not an applicant eligibility assessment.

    Camel-case aliases provide the integration boundary for Scout-style forms.
    The hackathon's persisted applicant state remains explicitly synthetic.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    roles: list[SearchText] = Field(min_length=1, max_length=5)
    keywords: list[SearchText] = Field(default_factory=list, max_length=12)
    exclude_keywords: list[SearchText] = Field(default_factory=list, max_length=12)
    locations: list[SearchText] = Field(default_factory=list, max_length=6)
    remote_ok: bool = False
    seniority: list[Seniority] = Field(default_factory=lambda: ["internship"], min_length=1, max_length=4)
    opportunity_types: list[OpportunityType] = Field(
        default_factory=lambda: ["company_roles", "research_programs"], min_length=1, max_length=2,
    )
    needs_visa_sponsorship: bool = False
    citizenship: SearchText | None = None
    funding: Literal["any", "paid", "fully_funded"] = "any"
    companies: list[SearchText] = Field(default_factory=list, max_length=8)


class SearchTask(BaseModel):
    model_config = ConfigDict(frozen=True)

    intent: Literal["ats", "web", "programs", "company"]
    query: str
    purpose: str
    label: str
    include_domains: tuple[str, ...] = ()
    exclude_domains: tuple[str, ...] = ()
    company: str | None = None


class RunBudget(BaseModel):
    """Scout's work ceilings, not permission to spend or proof of provider quotas.

    Agent integration must additionally enforce explicit authorization, shared
    budget reservations and status recovery before making any metered request.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_searches: int = Field(default=12, ge=0, le=12)
    max_fetch_urls: int = Field(default=45, ge=0, le=45)
    max_agent_runs: int = Field(default=2, ge=0, le=2)
    max_extractions: int = Field(default=36, ge=0, le=36)
    max_boards: int = Field(default=8, ge=0, le=8)
    max_postings_per_board: int = Field(default=5, ge=0, le=5)
    max_leads: int = Field(default=10, ge=0, le=10)
    max_rechecks: int = Field(default=6, ge=0, le=6)
    agent_max_duration_seconds: int = Field(default=120, ge=1, le=120)
    soft_deadline_ms: int = Field(default=150_000, ge=1, le=150_000)
    hard_deadline_ms: int = Field(default=270_000, ge=1, le=270_000)

    @model_validator(mode="after")
    def validate_deadline_order(self) -> Self:
        if self.soft_deadline_ms > self.hard_deadline_ms:
            raise ValueError("Soft deadline cannot be later than the hard deadline.")
        return self


class WebPage(BaseModel):
    snapshot: SourceSnapshot
    requested_url: str
    links: list[str] = Field(default_factory=list)
    json_body: dict | list | None = None


class SourceLead(BaseModel):
    url: str
    title: str = ""
    organization: str | None = None
    location: str | None = None
    kind: Literal["posting", "board", "page"] = "page"
    via: Literal["search", "feed", "link", "agent"] = "search"
    source_url: str = ""
    # Optional source context; old persisted Agent/search leads remain valid.
    snippet: str | None = None
    intent: Literal["ats", "web", "programs", "company"] | None = None
    description: str | None = None
    employment_type: str | None = None
    posted_at: str | None = None
    remote: bool | None = None
    evidence_page: WebPage | None = None
    evidence_transform: str | None = None


class DiscoveryListing(BaseModel):
    """Discovery labels are not certified eligibility or application readiness."""

    id: str = ""
    title: str
    organization: str = "Unknown"
    kind: Literal["job", "program"] = "job"
    locations: list[str] = Field(default_factory=list)
    work_mode: Literal["onsite", "hybrid", "remote", "unknown"] = "unknown"
    seniority: Literal["internship", "new_grad", "entry_level", "experienced", "unknown"] = "unknown"
    cycle: str = "unknown"
    deadline_text: str | None = None
    deadline_precision: Literal["exact", "date", "month", "rolling", "unknown"] = "unknown"
    call_status: Literal["open", "closed", "future", "unknown"] = "unknown"
    visa_status: Literal["sponsors", "not_sponsored", "citizens_only", "unknown"] = "unknown"
    visa_note: str | None = None
    funding_level: Literal["fully_funded", "paid", "unpaid", "unknown"] = "unknown"
    stipend: bool | None = None
    travel: bool | None = None
    housing: bool | None = None
    round_trip_travel: bool | None = None
    filter_evidence: dict[str, list[str]] = Field(default_factory=dict)
    constraint_status: Literal["match", "needs_review", "excluded"] = "needs_review"
    constraint_reasons: list[str] = Field(default_factory=list)
    enrichment_status: Literal["pending", "complete", "partial", "failed", "cached"] = "pending"
    score_mode: Literal["rules", "groq", "cached"] = "rules"
    score_breakdown: dict[str, int] = Field(default_factory=dict)
    evidence_completeness: dict[str, str] = Field(default_factory=dict)
    funding_note: str | None = None
    eligibility: str | None = None
    summary: str = ""
    apply_url: str
    source_url: str
    checked_at: str
    found_via: Literal["search", "feed", "link", "agent"] = "search"
    verification: Literal["verified", "partial", "uncertain"] = "partial"
    requirements: list[Fact] = Field(default_factory=list)
    score: int = Field(default=0, ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)
    is_new: bool = False
    saved: bool = False
    hidden: bool = False


class ExtractionResult(BaseModel):
    page_type: Literal["posting", "program", "index", "closed", "other"] = "other"
    listings: list[DiscoveryListing] = Field(default_factory=list)
    leads: list[SourceLead] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class MatchVerdict(BaseModel):
    role_fit: Literal["strong", "partial", "weak", "none"] = "weak"
    location_fit: Literal["match", "remote_ok", "mismatch", "unknown"] = "unknown"
    eligibility_fit: Literal["eligible", "ineligible", "unknown"] = "unknown"
    reason: str = ""


class RunEvent(BaseModel):
    stage: str
    message: str
    url: str = ""
    timestamp: str = ""


class EngineResult(BaseModel):
    listings: list[DiscoveryListing] = Field(default_factory=list)
    pages: list[WebPage] = Field(default_factory=list)
    events: list[RunEvent] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    usage: dict[str, int] = Field(default_factory=dict)
    partial: bool = False
