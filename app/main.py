from __future__ import annotations

from dataclasses import replace
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent import AgentError, run_agent, summarize_context, summarize_plan
from .config import ROOT, settings
from .graph import GraphStore
from .models import ChangeImpact, DiscoveryResult, Plan, ProfileState
from .planner import build_plan
from .sources import DiscoverService

app = FastAPI(title="Just Chill · Internship preparation", version="0.1.0")
store = GraphStore(settings)
simulation = GraphStore(replace(settings, db_graph=settings.db_graph + "_simulation"))
sources = DiscoverService(settings)
STATIC = ROOT / "app" / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class DiscoverRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)


class PlanRequest(BaseModel):
    selected_ids: list[str] = Field(min_length=1, max_length=3)
    profile: ProfileState = Field(default_factory=ProfileState)


class AgentRequest(PlanRequest):
    message: str = Field(default="Create a preparation plan and explain the next useful action.", max_length=2000)


class RefreshRequest(BaseModel):
    url: str = Field(min_length=10, max_length=2000)


class SimulationRequest(PlanRequest):
    opportunity_id: str
    fact_name: str = "reference_min"
    value: Any = 2


def safe_failure(exc: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail=f"{type(exc).__name__}: service unavailable; no acceptance performed.")


def validate_targets(ids: list[str], db: GraphStore = store) -> list[str]:
    unique = list(dict.fromkeys(ids))
    for target_id in unique:
        try:
            found = db.get_opportunity(target_id)
        except Exception as exc:
            raise safe_failure(exc) from None
        if not found:
            raise HTTPException(404, f"Unknown target: {target_id}")
    return unique


def make_plan(request: PlanRequest, db: GraphStore = store,
              impact: ChangeImpact | None = None) -> Plan:
    if not request.profile.synthetic:
        raise HTTPException(400, "This hackathon demo accepts synthetic profiles only.")
    ids = validate_targets(request.selected_ids, db)
    previous = db.latest_plan(request.profile.id)
    proposal = build_plan(db.context(ids), request.profile, previous=previous, impact=impact)
    return db.save_plan(proposal)


def persist_discovery(result: DiscoveryResult) -> dict[str, Any]:
    snapshots = {s.url: s for s in result.snapshots}
    impacts = []
    existing_records = store.list_opportunities()
    uncertainty_impacts = []
    if result.mode == "live":
        for outcome in result.source_outcomes:
            # A previously observed cohort disappearing is a source gap, not repeal.
            prior = [o for o in existing_records if o.source_url == outcome.url
                     or any(f.source_url == outcome.url for f in o.facts)]
            if outcome.status == "failed":
                uncertainty_impacts.append(store.mark_source_uncertain(outcome.url).model_dump(mode="json"))
                continue
            returned_ids = set(outcome.opportunity_ids)
            for previous in prior:
                if previous.source_url != outcome.url or previous.id in returned_ids:
                    continue
                retained = previous.model_copy(deep=True)
                retained.verification = "uncertain"
                for fact in retained.facts:
                    if fact.source_url == outcome.url:
                        fact.status = "unknown"
                uncertainty_impacts.append(store.upsert_opportunity(retained).model_dump(mode="json"))
    for opportunity in result.opportunities:
        existing = store.get_opportunity(opportunity.id)
        if existing is not None and opportunity.mode == "cached" and existing.mode == "live":
            # Loading examples must not roll back a newer successful live refresh.
            opportunity = existing
            impacts.append({"skipped_cached_rollback": opportunity.id})
            continue
        impacts.append(store.upsert_opportunity(
            opportunity, snapshots.get(opportunity.source_url)).model_dump(mode="json"))
    payload = result.model_dump(mode="json")
    payload["opportunities"] = [store.get_opportunity(o.id).model_dump(mode="json")
                                for o in result.opportunities]
    return {**payload, "impacts": impacts, "uncertainty_impacts": uncertainty_impacts}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    try:
        db = store.health()
    except Exception:
        db = {"healthy": False}
    return {"database": db, "provider_configured": {"groq": bool(settings.groq_key),
             "tinyfish": bool(settings.tinyfish_key)}, "synthetic_profile_only": True,
            "app_version": "0.1.0"}


@app.get("/api/opportunities")
def opportunities():
    try:
        return {"opportunities": [o.model_dump(mode="json") for o in store.list_opportunities()]}
    except Exception as exc:
        raise safe_failure(exc)


@app.post("/api/discover")
def discover(request: DiscoverRequest):
    try:
        return persist_discovery(sources.discover(request.query, limit=4))
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        raise safe_failure(exc)


@app.post("/api/examples")
def examples():
    try:
        return persist_discovery(sources.load_examples())
    except Exception as exc:
        raise safe_failure(exc)


@app.post("/api/plan")
def plan(request: PlanRequest):
    try:
        return make_plan(request).model_dump(mode="json")
    except HTTPException:
        raise
    except Exception as exc:
        raise safe_failure(exc)


@app.get("/api/plan/latest")
def latest_plan(profile_id: str = "demo-student", mode: str = "official"):
    try:
        found = (simulation if mode == "simulation" else store).latest_plan(profile_id)
        return {"plan": found.model_dump(mode="json") if found else None}
    except Exception as exc:
        raise safe_failure(exc)


@app.post("/api/plan/{plan_id}/accept")
def accept_plan(plan_id: str, mode: str = "official"):
    try:
        accepted = (simulation if mode == "simulation" else store).accept_plan(plan_id)
        return accepted.model_dump(mode="json")
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(409, str(exc)[:300])
    except Exception as exc:
        raise safe_failure(exc)


@app.post("/api/refresh")
def refresh(request: RefreshRequest):
    try:
        result = sources.refresh(request.url)
        if result.errors and not result.source_outcomes:
            impact = store.mark_source_uncertain(request.url)
            return {**result.model_dump(mode="json"), "uncertainty_impact": impact.model_dump(mode="json")}
        return persist_discovery(result)
    except Exception as exc:
        raise safe_failure(exc)


@app.post("/api/simulate")
def simulate(request: SimulationRequest):
    # A separate graph keeps the demonstration from altering official source data.
    if not request.profile.synthetic:
        raise HTTPException(400, "Synthetic profiles only.")
    if request.fact_name not in {"reference_min", "statement_max_words", "application_deadline"}:
        raise HTTPException(400, "Unsupported simulated field.")
    ids = validate_targets(request.selected_ids)
    if request.opportunity_id not in ids:
        raise HTTPException(400, "Choose a selected target for the simulation.")
    if request.fact_name in {"reference_min", "statement_max_words"}:
        if isinstance(request.value, bool) or not isinstance(request.value, int) or not 1 <= request.value <= 1000:
            raise HTTPException(400, "Simulation value must be an integer between 1 and 1000.")
    if request.fact_name == "application_deadline":
        from datetime import datetime
        try:
            parsed = datetime.fromisoformat(str(request.value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError()
        except ValueError:
            raise HTTPException(400, "Use a timezone-aware ISO deadline.") from None
    try:
        for target_id in ids:
            original = store.get_opportunity(target_id)
            cloned = original.model_copy(deep=True)
            cloned.mode = "synthetic"
            for fact in cloned.facts:
                fact.simulated = True
                fact.version_id = ""
            simulation.upsert_opportunity(cloned)
        before = make_plan(request, simulation)
        changed = simulation.get_opportunity(request.opportunity_id).model_copy(deep=True)
        current = next((f for f in changed.facts if f.name == request.fact_name), None)
        if current is None:
            raise HTTPException(400, "That source has no supported fact to simulate.")
        current.value = request.value
        current.status = "known"
        current.simulated = True
        current.excerpt = "SIMULATED policy change for the demonstration. Original official source is unchanged."
        changed.mode = "synthetic"
        impact = simulation.upsert_opportunity(changed)
        after = build_plan(simulation.context(ids), request.profile, previous=before, impact=impact)
        after.warnings.insert(0, "SIMULATION: altered policy is not a current official requirement.")
        after = simulation.save_plan(after)
        return {"mode": "simulation", "before": before.model_dump(mode="json"),
                "after": after.model_dump(mode="json"), "impact": impact.model_dump(mode="json"),
                "notice": "Separate simulation graph. Official data was not changed."}
    except HTTPException:
        raise
    except Exception as exc:
        raise safe_failure(exc)


@app.post("/api/agent")
def agent(request: AgentRequest):
    ids = validate_targets(request.selected_ids)
    if not request.profile.synthetic:
        raise HTTPException(400, "Synthetic profiles only.")

    def inspect() -> dict[str, Any]:
        context = store.context(ids)
        compact = summarize_context(context)
        return {"summary": f"Read {len(context.opportunities)} targets and {len(context.tasks)} graph-derived tasks.",
                "context": compact, "agent_context": compact}

    def propose() -> dict[str, Any]:
        proposal = make_plan(PlanRequest(selected_ids=ids, profile=request.profile))
        compact = summarize_plan(proposal)
        return {"summary": f"Proposed plan {proposal.id}; awaiting user acceptance.",
                "plan": proposal.model_dump(mode="json"), "agent_context": compact}

    def saved() -> dict[str, Any]:
        previous = store.latest_plan(request.profile.id)
        return {"summary": "Previous saved plan." if previous else "No previous plan.",
                "plan": previous.model_dump(mode="json") if previous else None,
                "agent_context": summarize_plan(previous) if previous else {"summary": "No previous plan."}}

    try:
        return run_agent(request.message, {"inspect_requirements": inspect,
                         "propose_plan": propose, "inspect_saved_plan": saved})
    except AgentError as exc:
        raise HTTPException(503, str(exc))
    except Exception as exc:
        raise safe_failure(exc)


@app.get("/api/graph")
def graph_view(ids: str = Query(default="")):
    selected = [i for i in ids.split(",") if i][:3]
    try:
        return store.graph_view(selected)
    except Exception as exc:
        raise safe_failure(exc)

