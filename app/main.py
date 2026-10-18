from __future__ import annotations

from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import threading
import time
import re
import inspect
import hashlib
import json
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent import AgentError, run_agent, summarize_context, summarize_plan
from .config import ROOT, settings
from .graph import GraphStore
from .models import ChangeImpact, DiscoveryResult, Plan, ProfileState, SourceOutcome
from .planner import build_plan
from .sources import DiscoverService
from .discovery.contracts import DiscoveryListing, DiscoveryPreferences, EngineResult
from .discovery.progressive import DiscoveryEngine
from .discovery.state import DiscoveryState, StateError
from .discovery.views import hunt_summary, listing_view
from .discovery.filters import classify_constraints, hydrate_filter_evidence

def drain_discovery(stop: threading.Event):
    # Two local workers, durable queued rows. Never recreate interrupted runs.
    in_flight=set()
    lock=threading.Lock()
    scheduler_checked=0.0
    def work(identifier):
        try:
            execute_discovery(identifier)
        finally:
            with lock:
                in_flight.discard(identifier)
    while not stop.is_set():
        try:
            if settings.discovery_refresh_enabled and time.monotonic()-scheduler_checked>=600:
                discovery_state.schedule_due()
                scheduler_checked=time.monotonic()
            with lock:
                for identifier in discovery_state.queued():
                    if identifier not in in_flight:
                        in_flight.add(identifier)
                        discovery_workers.submit(work,identifier)
        except Exception:
            # A damaged state DB is not a reason to resubmit provider requests.
            pass
        stop.wait(0.5)


@asynccontextmanager
async def lifespan(app):
    discovery_state.recover_interrupted()
    try:
        # Local graph migration only: no Search, Fetch, Groq or Agent call.
        # It lets saved source facts participate in the v0.7 learning roadmap.
        store.backfill_topics()
    except Exception:
        # Health and plan endpoints retain their explicit graph failure behavior.
        pass
    stop=threading.Event()
    drainer=threading.Thread(target=drain_discovery,args=(stop,),name="scout-queue",daemon=True)
    drainer.start()
    try:
        yield
    finally:
        stop.set()
        drainer.join(timeout=2)


app = FastAPI(title="PathWeave · Internship discovery and preparation", version="0.7.0",lifespan=lifespan)
store = GraphStore(settings)
simulation = GraphStore(replace(settings, db_graph=settings.db_graph + "_simulation"))
sources = DiscoverService(settings)
discovery_state = DiscoveryState(settings.discovery_state_path)
discovery_workers = ThreadPoolExecutor(max_workers=2, thread_name_prefix="scout-discovery")
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


class HuntRequest(BaseModel):
    name: str = Field(default="", max_length=120)
    preferences: DiscoveryPreferences


class ListingFlags(BaseModel):
    saved: bool = False
    hidden: bool = False


class ListingSelection(BaseModel):
    listing_ids: list[str] = Field(min_length=1, max_length=3)


def hunt_client(x_scout_client: str = Header(default="")) -> str:
    # Bearer token scopes discovery and preparation; never expose it in payloads.
    if not re.fullmatch(r"[a-zA-Z0-9_-]{24,80}", x_scout_client):
        raise HTTPException(400, "A valid browser discovery token is required.")
    return x_scout_client


def preparation_profile_id(token: str) -> str:
    return "browser-" + hashlib.sha256(hunt_client(token).encode()).hexdigest()


def scoped_request(request: PlanRequest, token: str) -> PlanRequest:
    if settings.demo_tools_enabled and not token:
        return request
    if request.profile.synthetic:
        raise HTTPException(400, "Use your own profile inputs for preparation.")
    request.profile = request.profile.model_copy(update={"id": preparation_profile_id(token), "synthetic": False})
    return request


def plan_store(mode: str) -> GraphStore:
    if mode == "official":
        return store
    if mode == "simulation" and settings.demo_tools_enabled:
        return simulation
    raise HTTPException(404, "Plan mode is unavailable.")


def execute_discovery(run_id: str):
    if not discovery_state.claim(run_id):
        return
    try:
        hunt = discovery_state.job_hunt(run_id)
        previous = [DiscoveryListing.model_validate(v) for v in (hunt["result"] or {}).get("listings", [])]
        from .discovery.contracts import WebPage
        previous_pages=[WebPage.model_validate(v) for v in (hunt["result"] or {}).get("pages",[])]
        engine=DiscoveryEngine(settings,discovery_state)
        options={"previous":previous,"previous_pages":previous_pages,"on_event":lambda event:discovery_state.event(run_id,event)}
        if "on_progress" in inspect.signature(engine.run).parameters:
            options["on_progress"]=lambda result:discovery_state.progress(run_id,result)
        result = engine.run(DiscoveryPreferences.model_validate(hunt["preferences"]),**options)
        failure = "No current listings could be verified. Review the source and provider diagnostics before another run." if result.usage.get("failed") else None
        discovery_state.finish(run_id,result,failure)
    except Exception as exc:
        # Never disclose provider bodies, tokens or private runtime paths.
        discovery_state.finish(run_id,None,f"{type(exc).__name__}: discovery could not complete. No application or plan acceptance performed.")


def submit_discovery(hunt_id: str, client: str) -> dict:
    run = discovery_state.enqueue(hunt_id,client)
    return run


def safe_failure(exc: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail=f"{type(exc).__name__}: service unavailable; no acceptance performed.")


def validate_targets(ids: list[str], db: GraphStore | None = None) -> list[str]:
    db = db or store
    unique = list(dict.fromkeys(ids))
    for target_id in unique:
        try:
            found = db.get_opportunity(target_id)
        except Exception as exc:
            raise safe_failure(exc) from None
        if not found:
            raise HTTPException(404, f"Unknown target: {target_id}")
    return unique


def make_plan(request: PlanRequest, db: GraphStore | None = None,
               impact: ChangeImpact | None = None) -> Plan:
    db = db or store
    ids = validate_targets(request.selected_ids, db)
    previous = db.latest_plan(request.profile.id)
    proposal = build_plan(db.context(ids), request.profile, previous=previous, impact=impact)
    return db.save_plan(proposal)


def persist_discovery(result: DiscoveryResult) -> dict[str, Any]:
    def target_snapshot(opportunity):
        candidates=[s for s in result.snapshots if s.url==opportunity.source_url]
        if not candidates:return None
        # Multiple decoded ATS rows can share a feed URL; evidence must bind to
        # this target's row, not whichever row happened to be returned last.
        return max(candidates,key=lambda s:sum(f.status=="known" and bool(f.excerpt) and f.excerpt in s.text for f in opportunity.facts))
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
            opportunity, target_snapshot(opportunity)).model_dump(mode="json"))
    payload = result.model_dump(mode="json")
    payload["opportunities"] = [store.get_opportunity(o.id).model_dump(mode="json")
                                for o in result.opportunities]
    return {**payload, "impacts": impacts, "uncertainty_impacts": uncertainty_impacts}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/interest-scenarios")
def interest_scenarios():
    return json.loads((ROOT / "app" / "interest" / "scenarios.json").read_text())


@app.get("/api/health")
def health():
    try:
        db = store.health()
    except Exception:
        db = {"healthy": False}
    return {"database": db, "provider_configured": {"groq": bool(settings.groq_key),
              "tinyfish": bool(settings.tinyfish_key)}, "synthetic_profile_only": False,
             "demo_tools_enabled": settings.demo_tools_enabled,
             "app_version": "0.7.0", "discovery": {"engine":"Progressive Search/Fetch/Agent with Groq requirements and preference fit",
                 "agent_enabled": settings.tinyfish_agent_enabled and (settings.tinyfish_agent_step_cap_verified or settings.tinyfish_agent_default_cap_verified),
                 "agent_gate": "Fallback requires available reserved budget; the configured account/default cap was verified separately from this status.",
                 "ai_tpm_budget":settings.discovery_ai_tpm,
                 "refresh_enabled": settings.discovery_refresh_enabled},
             "workspace_notice": "Hunts and plans belong to this browser. Profile and progress are self-reported; no personal documents are uploaded."}


@app.get("/api/hunts")
def list_hunts(x_scout_client: str = Header(default="")):
    return {"hunts":discovery_state.hunts(hunt_client(x_scout_client))}


@app.post("/api/hunts")
def create_hunt(request: HuntRequest, x_scout_client: str = Header(default="")):
    client=hunt_client(x_scout_client)
    try:
        hunt=discovery_state.create_hunt(client,request.preferences,request.name)
        return {"hunt":hunt,"run":submit_discovery(hunt["id"],client)}
    except StateError as exc:
        raise HTTPException(429,str(exc)) from None


@app.get("/api/hunts/{hunt_id}")
def get_hunt(hunt_id: str,x_scout_client: str = Header(default="")):
    try:
        record=discovery_state.hunt(hunt_id,hunt_client(x_scout_client))
        if record["result"]:
            preferences=DiscoveryPreferences.model_validate(record["preferences"])
            record["result"]["listings"]=[classify_constraints(v,preferences).model_dump(mode="json")
                                           for v in hunt_filter_listings(record)]
            # Full public snapshots stay server-side for evidence/bridge validation.
            record["result"].pop("pages",None)
        return record
    except StateError as exc:
        raise HTTPException(404,str(exc)) from None


def hunt_filter_listings(hunt: dict) -> list[DiscoveryListing]:
    from .discovery.contracts import WebPage
    result=hunt.get("result") or {}
    return hydrate_filter_evidence([DiscoveryListing.model_validate(v) for v in result.get("listings",[])],
                                  [WebPage.model_validate(p) for p in result.get("pages",[])])


@app.get("/api/hunts/{hunt_id}/listings")
def hunt_listings(hunt_id: str,view: str="visible",sort: str="match",q: str="",kind: str|None=None,
                  visa: str|None=None,funding: str|None=None,min_score: int=Query(default=0,ge=0,le=100),
                  x_scout_client: str=Header(default="")):
    if view not in {"visible","new","saved","hidden","review"} or sort not in {"match","newest","deadline"}:
        raise HTTPException(400,"Invalid listing view or sort.")
    if kind not in {None,"job","program"} or visa not in {None,"sponsors","not_restricted"} or funding not in {None,"paid","fully_funded"}:
        raise HTTPException(400,"Invalid listing filter.")
    try:
        hunt=discovery_state.hunt(hunt_id,hunt_client(x_scout_client))
    except StateError as exc:
        raise HTTPException(404,str(exc)) from None
    listings=hunt_filter_listings(hunt)
    preferences=DiscoveryPreferences.model_validate(hunt["preferences"])
    return {"listings":[v.model_dump(mode="json") for v in listing_view(listings,view=view,sort=sort,query=q,kind=kind,visa=visa,funding=funding,min_score=min_score,preferences=preferences)]}


@app.get("/api/hunts/{hunt_id}/summary")
def summary_hunt(hunt_id: str,x_scout_client: str=Header(default="")):
    try:
        hunt=discovery_state.hunt(hunt_id,hunt_client(x_scout_client))
    except StateError as exc:
        raise HTTPException(404,str(exc)) from None
    result=hunt["result"] or {}
    return hunt_summary(hunt_filter_listings(hunt),result.get("events",[]),DiscoveryPreferences.model_validate(hunt["preferences"]))


@app.get("/api/hunts/{hunt_id}/sources")
def sources_hunt(hunt_id: str,x_scout_client: str=Header(default="")):
    try:
        hunt=discovery_state.hunt(hunt_id,hunt_client(x_scout_client))
    except StateError as exc:
        raise HTTPException(404,str(exc)) from None
    result=hunt["result"] or {}
    sources={}
    for page in result.get("pages",[]):
        snapshot=page["snapshot"]
        sources[snapshot["url"]]={"url":snapshot["url"],"title":snapshot["title"],"checked_at":snapshot["checked_at"],"status":"read"}
    for event in result.get("events",[]):
        if event.get("url") and event["stage"]=="warning":
            sources.setdefault(event["url"],{"url":event["url"],"status":"gap","title":""})["note"]=event["message"]
    return {"sources":list(sources.values())}


@app.post("/api/hunts/{hunt_id}/runs")
def rerun_hunt(hunt_id: str,x_scout_client: str = Header(default="")):
    try:
        return submit_discovery(hunt_id,hunt_client(x_scout_client))
    except StateError as exc:
        raise HTTPException(429,str(exc)) from None


@app.get("/api/discovery-runs/{run_id}")
def discovery_run(run_id: str,x_scout_client: str = Header(default="")):
    try:
        return discovery_state.run(run_id,hunt_client(x_scout_client))
    except StateError as exc:
        raise HTTPException(404,str(exc)) from None


@app.post("/api/hunts/{hunt_id}/listings/{listing_id}/flags")
def listing_flags(hunt_id: str,listing_id: str,request: ListingFlags,x_scout_client: str = Header(default="")):
    try:
        discovery_state.flags(hunt_id,listing_id,hunt_client(x_scout_client),saved=request.saved,hidden=request.hidden)
        return {"saved":request.saved,"hidden":request.hidden}
    except StateError as exc:
        raise HTTPException(404,str(exc)) from None


@app.post("/api/hunts/{hunt_id}/select")
def select_listings(hunt_id: str,request: ListingSelection,x_scout_client: str = Header(default="")):
    from .discovery.bridge import listing_to_opportunities
    try:
        hunt=discovery_state.hunt(hunt_id,hunt_client(x_scout_client))
    except StateError as exc:
        raise HTTPException(404,str(exc)) from None
    if not hunt["result"]:
        raise HTTPException(409,"Wait for this hunt to return listings.")
    result=EngineResult.model_validate(hunt["result"])
    by_id={listing.id:listing for listing in result.listings}
    selected=[]
    enrichment_warnings=[]
    enrichment_deadline=time.monotonic()+120
    for listing_id in dict.fromkeys(request.listing_ids):
        listing=by_id.get(listing_id)
        if not listing:
            raise HTTPException(404,"Selected listing is not part of this hunt.")
        page_choices=[p for p in result.pages if p.snapshot.url==listing.source_url]
        normalize_title=lambda text:" ".join(text.split()).casefold()
        page=max(page_choices,key=lambda p:(normalize_title(p.snapshot.title)==normalize_title(listing.title),
            sum(bool(f.excerpt) and f.excerpt in p.snapshot.text for f in listing.requirements),p.snapshot.checked_at)) if page_choices else None
        from .discovery.urls import canonical_url
        historical=listing.verification=="uncertain" or any("Prior observation" in reason or "Earlier source observation" in reason for reason in listing.reasons)
        unbound_feed=bool(page and canonical_url(listing.apply_url) not in {canonical_url(page.snapshot.url),canonical_url(page.requested_url)}
            and not (normalize_title(page.snapshot.title)==normalize_title(listing.title) and "Evidence view:" in page.snapshot.text))
        if historical or unbound_feed:
            # Prior snapshots and a raw multi-job feed cannot become freshly
            # verified requirements merely because they exist in the cache.
            page=None
            listing=listing.model_copy(update={"requirements":[]})
        if not listing.requirements:
            from .discovery.provider import DiscoveryWebClient,ProviderError
            from .discovery.extract import ListingExtractor
            from .discovery.contracts import SourceLead
            if page is None:
                try:
                    if discovery_state.reserve("fetch_urls",1,settings.discovery_daily_fetch_urls):
                        fetched,failures=DiscoveryWebClient(settings).fetch([listing.apply_url],ttl=0)
                        enrichment_warnings.extend(failures.values())
                        if fetched:
                            page=fetched[0];listing.source_url=page.snapshot.url
                            result.pages.append(page)
                except ProviderError as exc:enrichment_warnings.append(str(exc))
            if page and time.monotonic()<enrichment_deadline:
                from .sources import parse_snapshot
                adapted=[o for o in parse_snapshot(page.snapshot) if not o.id.startswith("source-")]
                if not adapted:
                    def admit():
                        from .discovery.ai import AIError
                        if not discovery_state.reserve("ai_calls",1,settings.discovery_daily_ai_calls):
                            raise AIError("Daily AI allowance exhausted; target details remain unknown.",code="budget")
                    preferences=DiscoveryPreferences.model_validate(hunt["preferences"])
                    extractor=ListingExtractor(settings)
                    if hasattr(extractor, "extract_selected"):
                        details=extractor.extract_selected(page,listing,preferences,
                            remaining_seconds=max(0,enrichment_deadline-time.monotonic()),on_call=admit)
                    else:
                        details=extractor.extract(page,preferences,
                            SourceLead(url=listing.apply_url,title=listing.title,organization=listing.organization,kind="posting",via=listing.found_via),
                            remaining_seconds=max(0,enrichment_deadline-time.monotonic()),on_call=admit)
                    enrichment_warnings.extend(details.warnings)
                    normalize=lambda value:re.sub(r"[^a-z0-9]+"," ",value.casefold()).strip()
                    match=next((value for value in details.listings if normalize(value.title)==normalize(listing.title)),None)
                    established_cycle=listing.cycle
                    if match and established_cycle!="unknown" and match.cycle not in {"unknown",established_cycle}:
                        enrichment_warnings.append("Extractor returned a different cohort; target identity preserved and requirements remain unverified.")
                        match=None
                    if match:
                        # The user selected this actual posting, not a new AI-made link.
                        match.apply_url=listing.apply_url;match.id=listing.id
                        match.cycle=established_cycle
                        listing=match
                    else:enrichment_warnings.append("Selected posting details could not be verified; listing retained with unknown requirements.")
            elif page is None:enrichment_warnings.append("Posting could not be read; your target is retained but preparation requirements are unknown.")
        for opportunity in listing_to_opportunities(listing,page):
            selected.append(opportunity)
    selected=list({o.id:o for o in selected}.values())
    if not 1 <= len(selected) <= 3:
        raise HTTPException(409,"Choose at most three explicit preparation targets/cohorts.")
    payload=persist_discovery(DiscoveryResult(query="explicit hunt selection",opportunities=selected,
                                             snapshots=[p.snapshot for p in result.pages],mode="live"))
    return {**payload,"selected_ids":[o.id for o in selected],"enrichment_warnings":list(dict.fromkeys(enrichment_warnings))}


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
    if not settings.demo_tools_enabled:
        raise HTTPException(404, "Cached examples are disabled during normal use.")
    try:
        return persist_discovery(sources.load_examples())
    except Exception as exc:
        raise safe_failure(exc)


@app.post("/api/plan")
def plan(request: PlanRequest, x_scout_client: str = Header(default="")):
    try:
        return make_plan(scoped_request(request, x_scout_client)).model_dump(mode="json")
    except HTTPException:
        raise
    except Exception as exc:
        raise safe_failure(exc)


@app.get("/api/plan/latest")
def latest_plan(profile_id: str | None = None, mode: str = "official", x_scout_client: str = Header(default="")):
    db = plan_store(mode)
    owner = profile_id if settings.demo_tools_enabled and not x_scout_client else preparation_profile_id(x_scout_client)
    if profile_id and profile_id != owner:
        raise HTTPException(404, "Plan not found in this browser.")
    try:
        found = db.latest_plan(owner or "demo-student")
        return {"plan": found.model_dump(mode="json") if found else None}
    except Exception as exc:
        raise safe_failure(exc)


@app.post("/api/plan/{plan_id}/accept")
def accept_plan(plan_id: str, mode: str = "official", x_scout_client: str = Header(default="")):
    db = plan_store(mode)
    owner = None if settings.demo_tools_enabled and not x_scout_client else preparation_profile_id(x_scout_client)
    try:
        if owner:
            existing = db.get_plan(plan_id)
            if existing is None or existing.profile.id != owner:
                raise HTTPException(404, "Plan not found in this browser.")
        accepted = db.accept_plan(plan_id)
        return accepted.model_dump(mode="json")
    except HTTPException:
        raise
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(409, str(exc)[:300])
    except Exception as exc:
        raise safe_failure(exc)


@app.post("/api/refresh")
def refresh(request: RefreshRequest):
    try:
        prior=[o for o in store.list_opportunities() if o.source_url==request.url and o.id.startswith("listing-") and o.discovery]
        if prior:
            return refresh_discovered_targets(request.url,prior)
        result = sources.refresh(request.url)
        if result.errors and not result.source_outcomes:
            impact = store.mark_source_uncertain(request.url)
            return {**result.model_dump(mode="json"), "uncertainty_impact": impact.model_dump(mode="json")}
        return persist_discovery(result)
    except Exception as exc:
        raise safe_failure(exc)


def refresh_discovered_targets(url: str, prior: list) -> dict:
    """Refresh selected generic targets without substituting a source-* identity."""
    from .discovery.bridge import listing_to_opportunities
    from .discovery.contracts import SourceLead
    from .discovery.extract import ListingExtractor
    from .discovery.provider import DiscoveryWebClient, ProviderError
    from .discovery.urls import canonical_url
    errors=[]
    pages=[]
    opportunities=[]
    if not discovery_state.reserve("fetch_urls",1,settings.discovery_daily_fetch_urls):
        errors.append("Daily discovery Fetch allowance reached; retained requirements need review.")
    else:
        try:
            pages,failures=DiscoveryWebClient(settings).fetch([url])
            errors.extend(failures.values())
        except ProviderError as exc:
            errors.append(str(exc))
    for old in prior:
        if not pages or not discovery_state.reserve("ai_calls",1,settings.discovery_daily_ai_calls):
            errors.append("Generic source extraction unavailable; retained evidence is uncertain.")
            continue
        page=pages[0]
        metadata=DiscoveryListing.model_validate(old.discovery)
        prefs=DiscoveryPreferences(roles=[old.program[:120]],opportunity_types=["company_roles" if old.category=="Company" else "research_programs"])
        extractor=ListingExtractor(settings)
        if hasattr(extractor,"extract_selected"):
            extracted=extractor.extract_selected(page,metadata,prefs,remaining_seconds=90)
        else:
            extracted=extractor.extract(page,prefs,SourceLead(url=url,title=old.program,organization=metadata.organization,kind="posting"))
        errors.extend(extracted.warnings)
        for listing in extracted.listings:
            if canonical_url(listing.apply_url)!=canonical_url(metadata.apply_url):
                continue
            for candidate in listing_to_opportunities(listing,page):
                if candidate.id==old.id:
                    opportunities.append(candidate)
    status="failed" if not pages else "partial" if len(opportunities)<len(prior) or errors else "success"
    result=DiscoveryResult(query="selected generic source refresh",opportunities=opportunities,
        snapshots=[p.snapshot for p in pages],source_outcomes=[SourceOutcome(url=url,status=status,
            opportunity_ids=[o.id for o in opportunities],errors=list(dict.fromkeys(errors)))],errors=list(dict.fromkeys(errors)),mode="live")
    return persist_discovery(result)


@app.post("/api/simulate")
def simulate(request: SimulationRequest):
    if not settings.demo_tools_enabled:
        raise HTTPException(404, "Policy simulation is disabled during normal use.")
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
def agent(request: AgentRequest, x_scout_client: str = Header(default="")):
    request = scoped_request(request, x_scout_client)
    ids = validate_targets(request.selected_ids)

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
