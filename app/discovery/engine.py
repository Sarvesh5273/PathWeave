"""Scout-style staged discovery; budgets, traces and degraded behavior are explicit.

Root-owned integration of new collection, extraction/ranking and browser modules.
This engine never certifies an application or accepts a preparation plan.
"""
from __future__ import annotations

import hashlib
import inspect
import math
import re
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode, urlsplit

from app.config import Settings
from app.models import utc_now
from app.sources import _application_url, parse_snapshot

from .ai import AIError
from .browser import BrowserFallback
from .contracts import DiscoveryListing, DiscoveryPreferences, EngineResult, ExtractionResult, RunBudget, RunEvent, SourceLead, WebPage
from .extract import ListingExtractor
from .feeds import MAX_FEED_ROWS, _json_body, parse_feed
from .provider import DiscoveryWebClient, ProviderError
from .ranking import normalize_text, place_matches, rank_listings, role_relevance
from .search_plan import plan_searches
from .state import DiscoveryState
from .urls import _base_domain, canonical_url, classify_url, detect_ats, posting_links


TERMINAL_PROVIDER_ERRORS = {"HTTP_401", "HTTP_402", "HTTP_403"}
MAX_RESULTS = 60
AGENT_PENDING_SECONDS = 10**9  # Unknown starts require operator reconciliation, not TTL retry.


def _cycle(value: str) -> str:
    return re.sub(r"[^\w+#]+", " ", value.casefold()).strip() or "unknown"


def _identity(listing: DiscoveryListing) -> str | None:
    url = canonical_url(listing.apply_url)
    return url + "|" + _cycle(listing.cycle) if url else None


def _timed_call(function, *args, remaining_seconds: float, **kwargs):
    """Keep older injected adapters compatible without catching their TypeErrors."""
    parameters = inspect.signature(function).parameters
    if "remaining_seconds" in parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in parameters.values()):
        kwargs["remaining_seconds"] = max(0.0, remaining_seconds)
    return function(*args, **kwargs)


def _uncertain(listing: DiscoveryListing, reason: str) -> DiscoveryListing:
    retained = listing.model_copy(deep=True)
    retained.verification = "uncertain"
    if retained.call_status != "closed":
        retained.call_status = "unknown"
    retained.visa_status = "unknown"
    retained.funding_level = "unknown"
    retained.stipend = retained.travel = retained.housing = None
    retained.deadline_precision = "unknown"
    retained.score = 0
    retained.reasons = [reason, *[r if r.startswith("Prior (not current): ") else "Prior (not current): " + r
                                 for r in retained.reasons if r != reason]]
    for fact in retained.requirements:
        # Keep the prior quote/source/version for history, never as current truth.
        fact.status, fact.value = "unknown", None
    return retained


INTERN_TITLE = re.compile(r"\b(?:intern\w*|co ?op|stagiaire|stage|praktikum|praktikant|werkstudent|working student|trainee|placement|summer (?:student|analyst|associate|research|fellow)|research fellow|fellowship|scholar)\b")
EARLY_TITLE = re.compile(r"\b(?:new grad|graduate|university|campus|early career|entry level|class of 20\d\d|20\d\d start|junior|associate|engineer i)\b")
SENIOR_TITLE = re.compile(r"\b(?:senior|sr|staff|principal|lead|manager|director|head|vp|vice president|architect|distinguished)\b")
CAREERS_HINT = re.compile(r"career|jobs?|join|work-with-us|opportunit|vacanc|recruit|hiring|position|intern|students?|graduate|university|early-?career", re.I)
PROGRAM_HINT = re.compile(r"program|programme|intern|fellow|scholar|research|summer|reu|exchange|visiting|student", re.I)
PAGE_ORDER = {"company": 0, "programs": 1, "web": 2, "ats": 3, None: 2}


def _relevance(preferences: DiscoveryPreferences, lead: SourceLead):
    title = normalize_text(lead.title)
    extra = (lead.description or lead.snippet or "")[:1500]
    intern, early = bool(INTERN_TITLE.search(title)), bool(EARLY_TITLE.search(title))
    off_target = ("experienced" not in preferences.seniority and bool(SENIOR_TITLE.search(title)) and not intern) or bool(re.search(r"\b(?:high school|secondary school|apprentice|apprenticeship)\b", title))
    excluded = any(re.search(r"\b" + re.escape(normalize_text(k)) + r"\b", title) for k in preferences.exclude_keywords if normalize_text(k))
    role = role_relevance(preferences, lead.title, extra)
    keyword = any(normalize_text(k) in normalize_text(lead.title + " " + extra) for k in preferences.keywords)
    location = lead.location or lead.snippet or lead.title
    location_fit = bool(preferences.locations and (any(place_matches(p, location) for p in preferences.locations) or preferences.remote_ok and re.search(r"\bremote\b", location, re.I)))
    level_fit = intern and "internship" in preferences.seniority or early and any(s in preferences.seniority for s in ("new_grad", "entry_level")) or not intern and "experienced" in preferences.seniority
    score = role * 3 + (1.5 if level_fit else 0) + (1 if location_fit else 0) + (0.5 if keyword else 0) - (4 if off_target else 0)
    plausible = not excluded and not off_target and (role >= 0.5 or keyword and role > 0) and ("experienced" in preferences.seniority or ("internship" in preferences.seniority if intern else any(s in preferences.seniority for s in ("new_grad", "entry_level"))))
    return score, excluded or off_target, plausible


def _lead_priority(preferences: DiscoveryPreferences, lead: SourceLead):
    context = " ".join([lead.location or "", lead.snippet or "", lead.title, lead.url])
    place_hint = any(place_matches(place, context) for place in preferences.locations)
    # Location hints order reading only. They never establish eligibility or a
    # posting's location without its retrieved source evidence.
    return (not place_hint if preferences.locations else False, lead.kind != "posting", -_relevance(preferences, lead)[0])


def _named_company(lead: SourceLead, companies: list[str]) -> str | None:
    ref = detect_ats(lead.url)
    slug = re.sub(r"[^a-z0-9]", "", (ref.org if ref else urlsplit(lead.url).hostname or "").casefold())
    for company in companies:
        token = normalize_text(company).replace(" ", "")
        if token and (token in slug or ref and len(slug) >= 4 and slug in token):
            return company
    return None


def _site(url: str) -> str:
    return _base_domain(url)


def _ai_failure(messages: list[str]) -> str | None:
    """Warnings about discarded evidence are not provider failures."""
    for message in messages:
        text = message.casefold()
        tag = re.search(r"\[ai:([a-z_]+)\]", text)
        if tag:
            if tag[1] in {"configuration", "authentication", "denied", "quota", "request"}:
                return "fatal"
            if tag[1] == "rate_limit" and re.search(r"quota/rate limit reached|persistent.*quota", text):
                return "quota"
            continue  # Page/response/deadline/admission failures are not permanent.
        if "groq" not in text:
            continue
        if re.search(r"authentication failed|denied the request|key is not configured|model is not configured|allowance or credits|could not be reached|unavailable|rejected the structured.output request", text):
            return "fatal"
        if re.search(r"persistent.*quota|quota.*persistent|daily.*(?:quota|limit)|(?:quota|rate limit).*exhausted", text):
            return "fatal"
        if re.search(r"quota|rate limit", text):
            return "quota"
    return None


class DiscoveryEngine:
    def __init__(self, settings: Settings, ledger: DiscoveryState, *, web=None, extractor=None, browser=None, ranking=None):
        self.settings = settings
        self.ledger = ledger
        self.web = web or DiscoveryWebClient(settings)
        self.extractor = extractor or ListingExtractor(settings)
        self.browser = browser or BrowserFallback(settings)
        self.ranking = ranking or rank_listings

    def run(self, preferences: DiscoveryPreferences, *, previous: list[DiscoveryListing] | None = None,
            previous_pages: list[WebPage] | None = None,
            budget: RunBudget | None = None, on_event: Callable[[RunEvent], None] | None = None) -> EngineResult:
        budget = budget or RunBudget()
        previous = previous or []
        prior = {_identity(v): v for v in previous if _identity(v)}
        result = EngineResult(pages=[p.model_copy(deep=True) for p in previous_pages or []],
                              usage={"searches":0,"fetch_urls":0,"extractions":0,"match_calls":0,"agent_runs":0})
        start = time.monotonic()
        seen_urls: set[str] = set()
        seen_boards: set[str] = set()
        candidates: dict[str, DiscoveryListing] = {}
        specificity: dict[str, tuple[int, bool, int]] = {}
        pending: list[SourceLead] = []
        agent_targets: dict[str, SourceLead] = {}
        ai_stopped = False
        ai_quota_failures = 0
        provider_stopped = False
        coverage_limited = False
        source_status: dict[str, str] = {}
        board_hits: dict[str, int] = {}
        search_failed = 0

        def event(stage: str, message: str, url: str = ""):
            item = RunEvent(stage=stage, message=message, url=url, timestamp=utc_now())
            result.events.append(item)
            if on_event:
                on_event(item)

        def warning(message: str, url: str = ""):
            result.errors.append(message)
            result.partial = True
            event("warning", message, url)

        def alive(soft: bool = False):
            return (time.monotonic()-start)*1000 < (budget.soft_deadline_ms if soft else budget.hard_deadline_ms)

        def remaining():
            return max(0.0, budget.hard_deadline_ms / 1000 - (time.monotonic() - start))

        def reserve_ai(count: int = 1):
            return self.ledger.reserve("ai_calls", count, self.settings.discovery_daily_ai_calls)

        def ai_options(function):
            parameters = inspect.signature(function).parameters
            if "on_call" not in parameters:
                return {}
            first = True
            def on_call():
                nonlocal first
                if not first and not reserve_ai():
                    raise AIError("Shared daily AI allowance reached before a paced retry; no request was made.", code="budget")
                first = False
                result.usage["ai_attempts"] = result.usage.get("ai_attempts", 0) + 1
            return {"on_call": on_call}

        def source(lead: SourceLead, status: str, message: str):
            source_status[lead.url] = status
            event("source", f"{lead.kind}/{lead.via}: {status} — {message}", lead.url)

        def observe_ai(messages: list[str]):
            nonlocal ai_stopped, ai_quota_failures
            failure = _ai_failure(messages)
            if failure == "quota":
                ai_quota_failures += 1
            elif failure is None:
                ai_quota_failures = 0
            if failure == "fatal" or ai_quota_failures >= 2:
                ai_stopped = True
                event("extract", "Further AI admissions stopped: fatal provider failure or persistent quota. Cached evidence and deterministic matching remain available.")

        def ranked_leads(leads: list[SourceLead], *, board: bool = False):
            unique = unseen_leads(leads)
            allowed = [lead for lead in unique if lead.kind != "posting" or (_relevance(preferences, lead)[2] if board else not _relevance(preferences, lead)[1])]
            if len(allowed) < len(unique):
                event("collect", f"Rejected {len(unique)-len(allowed)} off-target/excluded posting lead(s) before Fetch/AI allowances.")
            return sorted(allowed, key=lambda lead: _lead_priority(preferences, lead))

        def unseen_leads(leads: list[SourceLead]) -> list[SourceLead]:
            unique: dict[str, SourceLead] = {}
            for lead in leads:
                key = canonical_url(lead.url)
                if not key or key in seen_urls:
                    continue
                if key not in unique:
                    unique[key] = lead.model_copy(update={"url": key})
                else:
                    # Link collectors often supply less context than extraction/feed.
                    old = unique[key]
                    for field in ("title", "organization", "location", "source_url", "snippet", "intent", "description", "employment_type", "posted_at", "remote", "evidence_page", "evidence_transform"):
                        if not getattr(old, field) and getattr(lead, field):
                            setattr(old, field, getattr(lead, field))
            return list(unique.values())

        def adapter(page: WebPage, lead: SourceLead) -> list[DiscoveryListing]:
            try:
                opportunities = parse_snapshot(page.snapshot)
            except (ValueError, TypeError, IndexError):
                return []
            known = [o for o in opportunities if not o.id.startswith("source-")]
            listings = []
            for o in known:
                facts = {f.name:f for f in o.facts if f.status == "known"}
                deadline = facts.get("application_deadline")
                listings.append(DiscoveryListing(
                    id="listing-"+hashlib.sha256((o.source_url+o.id).encode()).hexdigest()[:20],
                    title=o.program, organization=o.program, kind="program" if o.category=="Research" else "job",
                    locations=[o.country] if o.country != "Unknown" else [], cycle=o.cycle,
                    seniority="internship", call_status=o.call_status, source_url=o.source_url,
                    apply_url=o.source_url, checked_at=o.checked_at, found_via=lead.via,
                    deadline_text=str(deadline.value) if deadline else None,
                    deadline_precision="exact" if deadline else "unknown",
                    summary=o.summary, requirements=o.facts, verification=o.verification,
                    funding_note=str(facts["funding"].value)[:300] if "funding" in facts else None,
                ))
            return listings

        def add_listing(listing: DiscoveryListing, *, final: bool = True, reviewed: bool = False):
            identity = _identity(listing)
            if not identity:
                warning("Rejected unsafe application link from extraction.")
                return
            application = canonical_url(listing.apply_url)
            if not final and application == canonical_url(listing.source_url):
                warning("Generic category/index page rejected as a selectable opening; follow a specific application lead.", listing.source_url)
                return
            if not final and _cycle(listing.cycle) == "unknown" and any(
                canonical_url(v.apply_url) == application and specificity[k][0] > 0
                for k, v in candidates.items()
            ):
                return  # A late unknown-cycle index cannot duplicate a final posting.
            listing = listing.model_copy(deep=True)
            listing.id = prior[identity].id if identity in prior and prior[identity].id else "listing-" + hashlib.sha256(identity.encode()).hexdigest()[:20]
            if identity in prior:
                listing.saved, listing.hidden = prior[identity].saved, prior[identity].hidden
            quality = (3 if reviewed else 2 if final else 0, final and listing.call_status == "closed",
                       sum(f.status == "known" and bool(f.excerpt) for f in listing.requirements))
            if not final:
                listing = _uncertain(listing, "Index-only summary: individual posting not verified; requirements are not current evidence.")
                listing.call_status = "unknown"  # A board cannot close a posting for us.
                listing.summary = "INDEX SUMMARY ONLY — individual posting not verified. " + listing.summary
            if identity not in candidates or quality >= specificity[identity]:
                candidates[identity], specificity[identity] = listing, quality
            if final and _cycle(listing.cycle) != "unknown":
                provisional = canonical_url(listing.apply_url) + "|unknown"
                if provisional in candidates and specificity[provisional][0] == 0:
                    del candidates[provisional], specificity[provisional]

        def browser_candidate(lead: SourceLead):
            ref = detect_ats(lead.url)
            if lead.kind == "posting" and (not ref or ref.readable):
                return  # A failed individual posting is not a careers-portal goal.
            company = _named_company(lead, preferences.companies)
            if not company and lead.organization:
                # Linked portals inherit a genuinely named company's page context.
                parent = classify_url(lead.source_url) if lead.source_url else None
                company = _named_company(parent, preferences.companies) if parent else None
            if company:
                target = lead.model_copy(update={"organization": company, "url": ref.board_url if ref and not ref.readable else lead.url})
                agent_targets.setdefault(company.casefold(), target)
                source(target, "needs_browser", "Named-company portal needs Agent; no claim of zero matching openings.")

        def extract(page: WebPage, lead: SourceLead):
            if not alive():
                warning("Structured extraction skipped after hard run deadline.", page.snapshot.url)
                return
            adapted = adapter(page, lead)
            if adapted:
                for listing in adapted:
                    add_listing(listing, reviewed=True)
                source(lead, "ok", f"Reviewed adapter established {len(adapted)} official cohort(s).")
                event("extract", f"Parsed {len(adapted)} official program cohort(s) with reviewed adapter.", page.snapshot.url)
                return
            key = "extract:v3-line-evidence:"+hashlib.sha256((page.snapshot.content_hash+page.snapshot.url+lead.model_dump_json()+preferences.model_dump_json()).encode()).hexdigest()
            cached = self.ledger.cached(key)
            if cached is not None:
                extracted = ExtractionResult.model_validate(cached)
                for listing in extracted.listings:
                    listing.checked_at = page.snapshot.checked_at
                event("extract", "Reused validated extraction of identical source content.", page.snapshot.url)
            elif ai_stopped or result.usage["extractions"] >= budget.max_extractions or not alive() or not reserve_ai():
                warning("Structured extraction skipped: run/daily AI budget, provider quota or deadline reached.", page.snapshot.url)
                source(lead, "skipped", "Extraction not attempted; try later after the allowance resets or verify provider configuration.")
                return
            else:
                result.usage["extractions"] += 1
                extracted = _timed_call(self.extractor.extract, page, preferences, lead, remaining_seconds=remaining(), **ai_options(self.extractor.extract))
                observe_ai(extracted.warnings)
                if extracted.listings or extracted.leads:
                    self.ledger.cache(key, extracted.model_dump(mode="json"), 86400)
                event("extract", f"Read {extracted.page_type}: {len(extracted.listings)} opening(s), {len(extracted.leads)} link(s).", page.snapshot.url)
                if not alive():
                    warning("Extraction returned at/after the hard deadline; no further AI work admitted.", page.snapshot.url)
            for message in extracted.warnings:
                warning(message, page.snapshot.url)
            for listing in extracted.listings:
                if lead.evidence_page is not None and lead.description and len(lead.description) > 200:
                    listing = listing.model_copy(update={"apply_url": lead.url, "source_url": page.snapshot.url, "found_via": "feed"})
                if extracted.page_type == "closed":
                    listing = listing.model_copy(update={"call_status": "closed"})
                add_listing(listing, final=extracted.page_type != "index")
            # Index listings need their own posting evidence before preparation.
            pending.extend(extracted.leads)
            if extracted.page_type == "index":
                pending.extend(SourceLead(url=v.apply_url,title=v.title,organization=v.organization,kind="posting",via="link",source_url=page.snapshot.url)
                               for v in extracted.listings if v.apply_url != page.snapshot.url)
            failed = bool(_ai_failure(extracted.warnings)) or any("[AI:" in m or "invalid structured" in m.casefold() or "invalid json" in m.casefold() for m in extracted.warnings)
            source(lead, "failed" if failed else "ok" if extracted.listings or extracted.leads else "empty",
                   "Extraction failed; source coverage is unknown." if failed else f"{extracted.page_type}: {len(extracted.listings)} opening(s), {len(extracted.leads)} follow-up link(s).")
            if failed:
                browser_candidate(lead)
            elif not extracted.listings and not extracted.leads:
                browser_candidate(lead)

        def read(leads: list[SourceLead], *, feed_ref=None):
            nonlocal provider_stopped, coverage_limited
            def fallback(lead: SourceLead):
                browser_candidate(SourceLead(url=feed_ref.board_url, organization=lead.organization, kind="board") if feed_ref else lead)
            available = max(0, budget.max_fetch_urls - result.usage["fetch_urls"])
            unique = unseen_leads(leads)
            chosen = unique[:available]
            coverage_limited |= len(chosen) < len(unique)
            for lead in unique[len(chosen):]:
                source(lead, "skipped", "Fetch work ceiling reached; this source was not read.")
            for offset in range(0, len(chosen), 10):
                batch = chosen[offset:offset+10]
                if provider_stopped or not alive():
                    warning("Fetch stage stopped at provider failure or hard run deadline.")
                    break
                if not self.ledger.reserve("fetch_urls",len(batch),self.settings.discovery_daily_fetch_urls) or not self.ledger.reserve("fetch_minute",len(batch),120,window=60):
                    warning("Fetch URL allowance/rate budget reached; remaining sources skipped.")
                    for lead in chosen[offset:]:
                        source(lead, "skipped", "Fetch allowance/rate budget denied admission; try after reset.")
                    break
                seen_urls.update(lead.url for lead in batch)
                result.usage["fetch_urls"] += len(batch)
                requests = [l.url for l in batch]
                if feed_ref and feed_ref.ats == "workday":
                    query = "intern" if "internship" in preferences.seniority else preferences.roles[0]
                    requests = [url + "?" + urlencode({"q": query}) for url in requests]
                try:
                    pages, failures = _timed_call(self.web.fetch, requests,
                                                 format="markdown", ttl=21600 if feed_ref else 86400 if all(l.kind == "posting" for l in batch) else 43200,
                                                 remaining_seconds=remaining())
                except ProviderError as exc:
                    warning(str(exc))
                    if exc.status in TERMINAL_PROVIDER_ERRORS:
                        provider_stopped = True
                    for lead in batch:
                        source(lead, "failed", "Provider request failed; check configuration or try later. No empty-opening claim.")
                        fallback(lead)
                    continue
                by_url = {l.url:l for l in batch}
                returned = {canonical_url(p.requested_url) for p in pages}
                failure_keys = {canonical_url(url) for url in failures}
                for lead in batch:
                    if lead.url not in returned and lead.url not in failure_keys:
                        failures[lead.url] = "Fetch returned no outcome for this requested source; coverage is unknown. Try again later."
                for url, message in failures.items():
                    warning(message, url)
                    if canonical_url(url) in by_url:
                        failed_lead = by_url[canonical_url(url)]
                        status = "blocked" if re.search(r"block|captcha|403|forbidden|denied|protection", message, re.I) else "failed"
                        source(failed_lead, status, message)
                        fallback(failed_lead)
                for page in pages:
                    lead = by_url.get(canonical_url(page.requested_url))
                    if lead is None or not canonical_url(page.snapshot.url):
                        warning("Rejected unsolicited or unsafe Fetch outcome; requested source remains unverified.")
                        continue
                    result.pages.append(page)
                    source(lead, "read", "Public snapshot retained with requested URL and retrieval time.")
                    event("fetch", "Read public source with links and retrieval timestamp.", page.snapshot.url)
                    if not alive():
                        warning("Fetched page retained, but further collection/extraction skipped after hard deadline.", page.snapshot.url)
                        continue
                    if feed_ref:
                        rows = ([v for v in posting_links(page) if (ref := detect_ats(v.url)) and ref.board_url == feed_ref.board_url and v.kind == "posting"]
                                if feed_ref.ats == "workday" else parse_feed(feed_ref, page))
                        raw_rows = None
                        if feed_ref.ats != "workday":
                            body = _json_body(page)
                            raw_rows = body if isinstance(body, list) else body.get("content" if feed_ref.ats == "smartrecruiters" else "jobs") if isinstance(body, dict) else None
                            if isinstance(raw_rows, list) and len(raw_rows) > MAX_FEED_ROWS:
                                coverage_limited = True
                                warning("ATS feed exceeded the bounded row safety limit; later rows were not evaluated. Coverage is partial.", page.snapshot.url)
                            if rows == [] and isinstance(raw_rows, list) and raw_rows:
                                rows = None  # Invalid rows are not evidence of an empty job board.
                        if rows is None:
                            warning("ATS feed could not be parsed; falling back to public board page.",page.snapshot.url)
                            pending.append(SourceLead(url=feed_ref.board_url,organization=lead.organization,kind="page",via="link"))
                            source(lead, "failed", "Malformed feed, not an empty board; public board fallback scheduled.")
                            browser_candidate(SourceLead(url=feed_ref.board_url,organization=lead.organization,kind="board"))
                        else:
                            relevant = ranked_leads(rows, board=True)
                            coverage_limited |= len(relevant) > budget.max_postings_per_board
                            chosen_rows = relevant[:budget.max_postings_per_board]
                            inline_pages = []
                            for row in chosen_rows:
                                if row.evidence_page is not None and row.description and len(row.description) > 200:
                                    seen_urls.add(row.url)
                                    inline_pages.append(row.evidence_page)
                                    event("feed", "Reading inline description from original feed; no posting Fetch required.", row.url)
                                    extract(row.evidence_page, row)
                                else:
                                    pending.append(row)
                            # One scoped, decoded evidence view per feed serves every selected
                            # title. Keep the original raw snapshot immediately before it.
                            if inline_pages:
                                text = "\n\n".join(p.snapshot.text for p in inline_pages)
                                result.pages.append(WebPage(snapshot=page.snapshot.model_copy(update={
                                    "title": "Decoded public ATS feed evidence (title-scoped rows)",
                                    "text": text, "content_hash": hashlib.sha256(text.encode()).hexdigest(),
                                }), requested_url=page.requested_url, links=[row.url for row in chosen_rows]))
                            source(lead, "ok" if rows else "empty", f"{len(rows)} board rows, {len(chosen_rows)} relevant selected, {len(inline_pages)} inline descriptions.")
                            event("feed", f"Collected {len(rows)} public ATS posting links; {len(relevant)} relevant, {len(chosen_rows)} selected before work allowances.", page.snapshot.url)
                    else:
                        links = ranked_leads(posting_links(page))
                        for link in links:
                            link.organization = link.organization or lead.organization
                            ref = detect_ats(link.url)
                            if ref and ref.org and ref.board_url not in seen_boards:
                                pending.append(SourceLead(url=ref.board_url, organization=_named_company(link, preferences.companies) or lead.organization or ref.organization,
                                                          kind="board", via="link", source_url=page.snapshot.url))
                        coverage_limited |= len(links) > budget.max_leads
                        pending.extend(links[:budget.max_leads])
                        extract(page, lead)

        event("plan", "Planning Scout-style searches across companies, ATS postings, public pages and research programs.")
        found_boards: dict[str, SourceLead] = {}
        found_postings: dict[str, SourceLead] = {}
        found_pages: dict[str, SourceLead] = {}
        planned = plan_searches(preferences)
        tasks = planned[:budget.max_searches]
        coverage_limited |= len(tasks) < len(planned)
        # Reserve atomically before dispatch; only four already-admitted queries can
        # finish after a terminal failure. Preserve planner order, not completion order.
        search_budget_stopped = False
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="scout-search") as pool:
            for offset in range(0, len(tasks), 4):
                if provider_stopped or search_budget_stopped or not alive():
                    warning("Search stage stopped at provider failure, allowance or hard deadline.")
                    break
                jobs = []
                for task in tasks[offset:offset+4]:
                    if not alive():
                        warning("Remaining searches skipped after hard deadline.")
                        break
                    if not self.ledger.reserve("searches",1,self.settings.discovery_daily_searches) or not self.ledger.reserve("search_minute",1,25,window=60):
                        warning("Search allowance/rate budget reached; remaining queries skipped.")
                        search_budget_stopped = True
                        break
                    result.usage["searches"] += 1
                    jobs.append((task, pool.submit(_timed_call, self.web.search, task, remaining_seconds=remaining())))
                for task, future in jobs:
                    try:
                        found = future.result()
                        event("search", f'{task.label}: "{task.query}" → {len(found)} URL(s).')
                        pages_taken = 0
                        page_cap = 2 if task.intent == "company" else 4 if task.intent == "programs" else 3
                        # Rank raw title evidence before per-query page selection;
                        # low-quality first hits must not consume all source slots.
                        for raw in sorted(found, key=lambda v: _lead_priority(preferences, v)):
                            lead = classify_url(_application_url(raw.url))
                            if lead:
                                lead.title, lead.source_url = raw.title, raw.source_url or lead.url
                                lead.snippet, lead.location, lead.intent = raw.snippet, raw.location, task.intent
                                ref = detect_ats(lead.url)
                                if ref:
                                    if ref.org:
                                        board_hits[ref.board_url] = board_hits.get(ref.board_url, 0) + 1
                                    company = _named_company(lead, preferences.companies)
                                    lead.organization = company or ref.organization
                                    if ref.org:
                                        found_boards.setdefault(ref.board_url, SourceLead(url=ref.board_url, organization=company or ref.organization, kind="board", intent=task.intent))
                                    if lead.kind == "posting":
                                        found_postings.setdefault(lead.url, lead)
                                    continue
                                lead.organization = _named_company(lead, preferences.companies) or (raw.organization if task.intent != "company" else None)
                                if lead.kind == "posting" and _relevance(preferences, lead)[1]:
                                    continue
                                hint = urlsplit(lead.url).path + " " + lead.title
                                useful = (PROGRAM_HINT.search(hint + " " + (lead.snippet or "")) if task.intent == "programs" else CAREERS_HINT.search(hint))
                                if task.intent == "company":
                                    useful = useful or bool(_named_company(lead, [task.company] if task.company else []))
                                if not useful or pages_taken >= page_cap:
                                    continue
                                target = found_postings if lead.kind == "posting" else found_pages
                                if lead.url in target:
                                    continue
                                if lead.kind != "posting" and sum(_site(v.url) == _site(lead.url) for v in found_pages.values()) >= 2:
                                    continue
                                target[lead.url] = lead
                                pages_taken += 1
                    except ProviderError as exc:
                        search_failed += 1
                        warning(str(exc))
                        if exc.status in TERMINAL_PROVIDER_ERRORS:
                            provider_stopped = True

        if search_failed and search_failed == result.usage["searches"]:
            warning("Every admitted search failed; discovery is unavailable, not an empty job market. Check TinyFish configuration or try again later.")
            result.usage["failed"] = 1
        event("collect", f"Classified {len(found_boards)} boards, {len(found_postings)} postings and {len(found_pages)} relevant public pages; source diversity applied before reading.")

        def wave(leads: list[SourceLead], *, first: bool = False, limit: int | None = None, allow_boards: bool = True):
            nonlocal coverage_limited
            unique = ranked_leads(leads)
            boards = [v for v in unique if v.kind == "board"]
            postings = [v for v in unique if v.kind == "posting"]
            pages = sorted([v for v in unique if v.kind == "page"], key=lambda v: PAGE_ORDER[v.intent])
            browser_boards = [v for v in boards if (ref := detect_ats(v.url)) and not ref.readable]
            for lead in browser_boards:
                browser_candidate(lead)
            boards = [v for v in boards if v not in browser_boards]
            boards.sort(key=lambda v: (-int(_named_company(v, preferences.companies) is not None), -board_hits.get(v.url, 0)))
            board_limit = (budget.max_boards if first else min(4, max(0, budget.max_boards-len(seen_boards)))) if allow_boards else 0
            posting_limit = 15 if first else limit if limit is not None else budget.max_postings_per_board*3
            page_limit = 10 if first else budget.max_leads
            coverage_limited |= len(boards) > board_limit or len(postings) > posting_limit or len(pages) > page_limit
            for lead in boards[board_limit:] + postings[posting_limit:] + pages[page_limit:]:
                source(lead, "skipped", "Source-selection ceiling reached; not read in this wave.")
            if not first:
                pending.extend(postings[posting_limit:] + pages[page_limit:])
            event("collect", f"{'First' if first else 'Follow-up'} wave: {min(len(boards), board_limit)} boards, {min(len(postings), posting_limit)} postings, {min(len(pages), page_limit)} pages selected; relevance precedes ceilings.")
            for lead in boards[:board_limit]:
                if provider_stopped or not alive():
                    warning("Collection wave stopped at provider failure or hard deadline.")
                    break
                ref = detect_ats(lead.url)
                if ref and not ref.readable:
                    browser_candidate(lead)
                elif ref and (ref.feed_url or ref.ats == "workday"):
                    if ref.board_url not in seen_boards and len(seen_boards)<budget.max_boards:
                        seen_boards.add(ref.board_url)
                        read([SourceLead(url=ref.feed_url or ref.board_url,organization=lead.organization,kind="page",via="feed")],feed_ref=ref)
            ordinary = []
            for lead in postings[:posting_limit] + pages[:page_limit]:
                ref = detect_ats(lead.url)
                if ref and not ref.readable and lead.via != "agent":
                    browser_candidate(lead)
                else:
                    ordinary.append(lead)
            read(sorted(unseen_leads(ordinary), key=lambda lead: _lead_priority(preferences, lead)))

        wave([*found_boards.values(), *found_postings.values(), *found_pages.values()], first=True)
        if alive(soft=True):
            following,pending = pending,[]
            wave(following, limit=budget.max_postings_per_board*3)
        else:
            warning("Optional second collection wave skipped after soft deadline.")

        for lead in list(agent_targets.values())[:budget.max_agent_runs]:
            key = "agent:"+self.browser.cache_key(lead,preferences)
            pending_key = "pending:" + key
            cached = self.ledger.cached(key)
            if cached is not None:
                pending.extend(SourceLead.model_validate(v) for v in cached)
                event("agent", "Reused cached Agent portal results (24-hour cache).",lead.url)
                source(lead, "ok" if cached else "empty", f"Actual cached Agent result: {len(cached)} opening link(s); no new run.")
                continue
            existing = self.ledger.cached(pending_key)
            if existing is not None:
                if not existing.get("run_id"):
                    warning("An Agent start is already claimed or has unknown outcome; reconcile before any retry. No automatic resubmission.", lead.url)
                    continue
                if provider_stopped or not alive(soft=True):
                    warning("Existing Agent recovery deferred after provider failure or soft deadline; no new run started.", lead.url)
                    continue
                recovery_key = "recovery:" + key
                if not self.ledger.acquire(recovery_key, {"run_id": existing["run_id"]}, 300):
                    warning("Another worker is recovering this Agent goal; no duplicate poll or run started.", lead.url)
                    continue
                try:
                    cached = self.ledger.cached(key)
                    if cached is not None:
                        pending.extend(SourceLead.model_validate(v) for v in cached)
                        continue
                    openings = _timed_call(self.browser.recover, existing["run_id"],
                                          SourceLead.model_validate(existing.get("lead", lead.model_dump())),
                                          remaining_seconds=remaining())
                    self.ledger.cache(key, [o.model_dump() for o in openings], 86400)
                    self.ledger.delete_cache(pending_key)
                    pending.extend(openings)
                    event("agent", f"Recovered {len(openings)} posting link(s) from the existing Agent run; no new run started.", lead.url)
                    source(lead, "ok" if openings else "empty", f"Recovered actual Agent result: {len(openings)} opening link(s).")
                except ProviderError as exc:
                    warning(str(exc) + f" Run ID: {existing['run_id']}; no new run started.", lead.url)
                    if exc.status in TERMINAL_PROVIDER_ERRORS:
                        provider_stopped = True
                finally:
                    self.ledger.delete_cache(recovery_key)
                continue
            if provider_stopped or not alive(soft=True):
                warning("Agent fallback skipped after provider failure or soft deadline.",lead.url)
                continue
            steps = self.settings.tinyfish_agent_max_steps
            custom_cap = self.settings.tinyfish_agent_step_cap_verified is True and type(steps) is int and 1 <= steps <= 500
            default_cap = getattr(self.settings, "tinyfish_agent_default_cap_verified", False) is True and type(steps) is int and steps == 150
            rate = getattr(self.settings, "tinyfish_agent_step_cost_usd", 0.016)
            valid_rate = type(rate) in (int, float) and math.isfinite(rate) and rate > 0
            if self.settings.tinyfish_agent_enabled is not True or not (custom_cap or default_cap) or not valid_rate:
                warning("Agent fallback available but live use is gated: enforceable step/spend cap not verified. Search/Fetch results remain usable.",lead.url)
                source(lead, "gated", "Browser stage unavailable until authorized, verified cap/rate configuration; not an empty board.")
                continue
            # Claim the goal before reserving money or sending a POST. A crash or
            # timeout without a run ID stays blocked until explicitly reconciled.
            record = {"run_id": None, "status": "unknown", "lead": lead.model_dump()}
            if not self.ledger.acquire(pending_key, record, AGENT_PENDING_SECONDS):
                warning("Another worker owns this Agent goal; no duplicate run started.", lead.url)
                continue
            cached = self.ledger.cached(key)
            if cached is not None:
                self.ledger.delete_cache(pending_key)
                pending.extend(SourceLead.model_validate(v) for v in cached)
                continue
            maximum = steps * rate
            if not self.ledger.reserve("agent_session_usd",maximum,self.settings.discovery_agent_budget_usd,window=10**15):
                self.ledger.delete_cache(pending_key)
                warning("Authorized total Agent budget exhausted; no new browser run started.",lead.url)
                continue
            if not alive():
                self.ledger.delete_cache(pending_key)
                warning("Agent start skipped after hard deadline.", lead.url)
                continue
            result.usage["agent_runs"] += 1
            try:
                def on_started(run_id: str):
                    record.update(run_id=run_id, status="RUNNING")
                    self.ledger.cache(pending_key, record, AGENT_PENDING_SECONDS)

                callbacks = {}
                if "on_started" in inspect.signature(self.browser.find).parameters:
                    callbacks["on_started"] = on_started
                openings = _timed_call(self.browser.find, lead, preferences, remaining_seconds=remaining(), **callbacks)
                self.ledger.cache(key,[o.model_dump() for o in openings],86400)
                self.ledger.delete_cache(pending_key)
                pending.extend(openings)
                event("agent",f"Browser found {len(openings)} posting link(s).",lead.url)
                source(lead, "ok" if openings else "empty", f"Actual Agent result: {len(openings)} opening link(s).")
            except ProviderError as exc:
                record["run_id"] = exc.run_id or record["run_id"] or getattr(self.browser, "last_run_id", None)
                record["status"] = exc.status or "unknown"
                self.ledger.cache(pending_key, record, AGENT_PENDING_SECONDS)
                warning(str(exc)+(f" Run ID: {record['run_id']}; recover status before any new run." if record["run_id"] else " Start outcome unknown; no automatic resubmission."),lead.url)
                if exc.status in TERMINAL_PROVIDER_ERRORS:
                    provider_stopped = True
        if not agent_targets:
            event("agent", "No named-company portal required browser fallback; Agent stage not applicable.")
        elif len(agent_targets) > budget.max_agent_runs:
            warning("Agent target ceiling reached; additional named-company portals remain unverified.")
        if pending and alive(soft=True):
            following,pending = pending,[]
            agent_leads = [lead for lead in following if lead.via == "agent"]
            wave([lead for lead in following if lead.via != "agent"], limit=min(6, budget.max_leads), allow_boards=False)
            read(ranked_leads(agent_leads))
            for lead in agent_leads:
                if source_status.get(canonical_url(lead.url)) in {"failed", "blocked"} and lead.title:
                    add_listing(DiscoveryListing(title=lead.title, organization=lead.organization or "Unknown",
                        locations=[lead.location] if lead.location else [], apply_url=lead.url,
                        source_url=lead.source_url or lead.url, checked_at=utc_now(), found_via="agent",
                        verification="uncertain", call_status="unknown", summary="AGENT OBSERVATION ONLY — posting Fetch failed; requirements and current application status remain unknown.",
                        reasons=["Actual Agent result retained; posting evidence unavailable."]))

        unseen = unseen_leads([SourceLead(url=v.apply_url,title=v.title,organization=v.organization,
                                         kind="posting",source_url=v.source_url) for v in previous])
        coverage_limited |= len(unseen) > budget.max_rechecks
        unseen = unseen[:budget.max_rechecks]
        if unseen and alive(soft=True):
            event("recheck",f"Rechecking {len(unseen)} previously visible opening(s).")
            read(unseen)
        elif unseen:
            warning("Old listing rechecks skipped after soft deadline; unseen listings are not declared closed.")
        else:
            event("recheck", "No unseen prior postings admitted for recheck; prior cohort history remains preserved.")

        for identity, listing in list(candidates.items()):
            if specificity[identity][0] == 0:
                warning("Index summary retained as uncertain: individual posting evidence was not verified.", listing.source_url)
        active = [listing for listing in candidates.values() if listing.call_status != "closed"]
        ranked = []
        for offset in range(0, len(active), 20):
            batch = active[offset:offset+20]
            ranking_settings = (self.settings if not ai_stopped and alive() and self.settings.groq_key and reserve_ai() else None)
            if ranking_settings:
                result.usage["match_calls"] += 1
            else:
                event("match", "Using labeled deterministic title/location fallback; AI unavailable, capped or past deadline.")
            rows = _timed_call(self.ranking, preferences, batch, settings=ranking_settings, remaining_seconds=remaining(), **(ai_options(self.ranking) if ranking_settings else {}))
            for listing in rows:
                original = candidates.get(_identity(listing))
                if original:
                    listing.reasons = list(dict.fromkeys([*original.reasons, *listing.reasons]))
            ranked.extend(rows)
            fallbacks = [reason for row in rows for reason in row.reasons if "Heuristic fallback" in reason]
            if fallbacks and ranking_settings:
                warning("AI matching failed or was unavailable; affected openings use labeled deterministic fallback.")
                observe_ai(list(dict.fromkeys(fallbacks)))
            if not alive():
                warning("Hard deadline reached; remaining matching uses deterministic fallback only.")
        ranked.sort(key=lambda listing: listing.score, reverse=True)
        if len(ranked) > MAX_RESULTS:
            event("match", f"Keeping Scout's top {MAX_RESULTS} current matches; lower-scoring observations are not active results.")
            ranked = ranked[:MAX_RESULTS]
        visible_ids = {_identity(v) for v in ranked}
        for identity, listing in candidates.items():
            if listing.call_status == "closed" or (identity in prior and identity not in visible_ids):
                historical = listing.model_copy(deep=True)
                historical.score = 0
                historical.reasons.insert(0, "Closed source observation; not an active match." if listing.call_status == "closed" else "Current observation retained for history; not an active match.")
                ranked.append(historical)
                visible_ids.add(identity)
        for identity, listing in prior.items():
            if identity not in visible_ids:
                retained = _uncertain(listing, "Prior observation retained: source/cohort was not revalidated this run; requirements are unknown.")
                if not retained.summary.startswith("UNVERIFIED PRIOR OBSERVATION — "):
                    retained.summary = "UNVERIFIED PRIOR OBSERVATION — " + retained.summary
                ranked.append(retained)
                warning("Prior listing retained as uncertain after a source or coverage gap.", retained.source_url)
        result.listings = ranked
        # New pages follow old ones so URL-based selection resolves to the latest
        # observation; distinct older snapshots remain available as prior evidence.
        pages = {}
        for page in result.pages:
            pages[(page.snapshot.url, page.snapshot.content_hash, page.snapshot.checked_at)] = page
        result.pages = list(pages.values())
        event("match",f"Deduplicated and ranked {len(candidates)} candidate(s); retained {len(result.listings)} active/historical listing(s).")
        if unseen_leads(pending):
            coverage_limited = True
        if coverage_limited or result.usage["fetch_urls"] >= budget.max_fetch_urls or result.usage["extractions"]>=budget.max_extractions:
            warning("One or more run work ceilings reached; coverage is partial.")
        result.errors=list(dict.fromkeys(result.errors))
        result.usage.update({"boards_discovered":len(found_boards), "postings_discovered":len(found_postings),
            "pages_discovered":len(found_pages), "sources_observed":len(source_status),
            "sources_failed":sum(status in {"failed", "blocked", "skipped", "gated", "needs_browser"} for status in source_status.values()),
            "sources_empty":sum(status == "empty" for status in source_status.values()),
            "leads_pending":len(unseen_leads(pending))})
        event("coverage", f"Search {result.usage['searches']}/{len(planned)} planned; boards {len(seen_boards)}/{len(found_boards)} discovered; Fetch {result.usage['fetch_urls']}/{budget.max_fetch_urls}; extraction {result.usage['extractions']}/{budget.max_extractions}; Agent {result.usage['agent_runs']}/{budget.max_agent_runs} (cached/recovered separately); matching {len(active)} candidates; {result.usage['sources_failed']} source gaps, {result.usage['leads_pending']} pending leads. Ceilings are not proof of complete coverage.")
        if result.usage.get("failed") or not candidates and result.partial:
            result.usage["failed"] = 1
            event("error", "No current openings could be established. Check source/provider diagnostics, try later when quotas reset, or revise role/place preferences. Prior observations are not fresh success.")
            event("done", "Discovery failed with visible source/provider gaps; no empty-market claim.")
        else:
            event("done", "Discovery complete with visible gaps." if result.partial else "Discovery complete. Review source requirements before selecting preparation targets.")
        return result
