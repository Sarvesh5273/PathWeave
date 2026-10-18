"""Find first, enrich selected targets later.

Search, public ATS feeds and fetched posting metadata produce cards without an LLM.
Unknown fields remain visible. Filter/ranking failure cannot erase a retrieved listing.
The earlier AI-first pipeline remains in engine.py for explicit advanced use.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable
from urllib.parse import urlsplit

from app.models import utc_now
from app.sources import _application_url, parse_snapshot

from .browser import BrowserFallback
from .contracts import DiscoveryListing, DiscoveryPreferences, EngineResult, RunEvent, SourceLead, WebPage
from .engine import _lead_priority, _named_company, _uncertain
from .feeds import parse_feed
from .provider import DiscoveryWebClient, ProviderError, _blocked_content
from .ranking import COUNTRY_ALIASES, COUNTRY_CITIES, place_matches, rank_listings, role_relevance
from .search_plan import plan_searches
from .state import DiscoveryState
from .urls import canonical_url, classify_url, detect_ats, posting_links
from .filters import source_filter_evidence, classify_constraints


INDEX_TITLE = re.compile(r"^(?:careers?(?:\s+at\s+.*)?|jobs|openings|opportunities|internships?|internship openings|search for jobs|search results|current vacancies)(?:\s*[|–—-].*)?$",re.I)
OPPORTUNITY = re.compile(r"\b(?:intern\w*|co[- ]?op|trainee|new[- ]?grad|fellowship|research (?:program|programme)|summer (?:research|student)|praktikum)\b",re.I)
NON_LISTING = re.compile(r"\b(?:list of|top \d+|best \d+|scholarships? corner|jobs in .+|how to|internships abroad|paid internship abroad|internship opportunities in)\b",re.I)
HTML_TITLE = re.compile(r"(?m)^\s*#\s+(.+?)\s*$")


def listing_id(url: str, cycle: str = "unknown") -> str:
    identity=(canonical_url(url) or url)+"|"+" ".join(cycle.casefold().split())
    return "listing-"+hashlib.sha256(identity.encode()).hexdigest()[:20]


def source_locations(text: str) -> list[str]:
    """Only named country/city strings that occur in supplied source text.

    City->country expansion is used for filtering later, not fabricated source labels.
    """
    locations=[]
    for country in dict.fromkeys([*COUNTRY_ALIASES,*COUNTRY_CITIES]):
        aliases=COUNTRY_ALIASES.get(country,[country])
        for alias in aliases:
            if len(alias)>=3 and re.search(r"(?<!\w)"+re.escape(alias)+r"(?!\w)",text,re.I):
                locations.append(country.title())
                break
    for cities in COUNTRY_CITIES.values():
        for city in cities.split("|"):
            if len(city)>=3 and re.search(r"(?<!\w)"+re.escape(city)+r"(?!\w)",text,re.I):
                locations.append(city.title())
    return list(dict.fromkeys(locations))[:8]


def source_listing(lead: SourceLead, page: WebPage | None = None) -> DiscoveryListing | None:
    """Metadata only, not inferred eligibility/visa/funding or preparation rules."""
    url=canonical_url(lead.url)
    if not url:return None
    ref=detect_ats(url)
    text=page.snapshot.text if page else ""
    title=lead.title
    if page:
        heading=HTML_TITLE.search(text)
        # A browser page title is stronger than a search snippet; no AI needed.
        title=heading[1] if heading else page.snapshot.title or title
        title=re.sub(r"\s*[|]\s*(?:.+?careers|.+?jobs).*$","",title,flags=re.I).strip()
    if not title.strip() or INDEX_TITLE.search(title) or NON_LISTING.search(title):return None
    if lead.kind!="posting" and re.search(r"\binternships\b",title,re.I) and not re.search(r"\b(?:program|programme|fellowship)\b",title,re.I):
        return None  # A category of internships is a link source, not one target.
    if lead.via=="feed" and not OPPORTUNITY.search(title) and (lead.employment_type or "").lower() in {"full-time","full time"}:return None
    if not OPPORTUNITY.search(title):
        # Non-intern roles still supported when a specific ATS posting is identified.
        if not ref or not ref.posting_url:return None
    if page and (_blocked_content(text) or len(text.strip())<100):return None
    if lead.kind not in {"posting"} and not (page and re.search(r"\b(?:apply|application|qualifications?|eligibility|requirements?|deadline)\b",text,re.I)):
        return None
    if lead.kind=="page" and re.search(r"github\.com|scholarshipscorner|gooverseas|interstride|studyabroad",url,re.I):return None
    organization=lead.organization or (ref.organization if ref and ref.organization else urlsplit(url).hostname or "Unknown")
    if not lead.organization and not ref:
        brand=re.search(r"\b(?:at|with|join)\s+([A-Z][A-Za-z0-9&.-]+(?:\s+[A-Z][A-Za-z0-9&.-]+)?)",title)
        if brand:organization=brand[1]
    # Only source title explicitly establishes a cycle; no query-year assumption.
    cycle_match=re.search(r"\b(?:Spring|Summer|Fall|Autumn|Winter)\s+20\d{2}\b|\b20\d{2}\b",title,re.I)
    cycle=cycle_match[0] if cycle_match else "unknown"
    # Feed metadata is actual source data. Search snippet locations remain hints,
    # not verified posting facts, and are therefore not filled here.
    locations=[lead.location] if lead.via=="feed" and lead.location else source_locations(title)
    if page:
        location_lines=[line for line in text.splitlines() if re.match(r"\s*(?:#{1,4}\s*)?(?:location|locations|place|based in)\b",line,re.I)]
        if location_lines:
            labels=[re.sub(r"^\s*(?:#{1,4}\s*)?locations?\s*[:\-]?\s*","",line,flags=re.I).strip() for line in location_lines]
            locations=[value[:120] for value in labels if value and not re.search(r"\b(?:unknown|not stated|not specified)\b",value,re.I)][:6]
        if not locations and not location_lines:
            # Read only the posting header for place metadata, not footer office lists.
            locations=source_locations(text[:900])
    kind="program" if lead.intent=="programs" or re.search(r"research (?:internship|program|fellow)|summer research",title,re.I) else "job"
    status="unknown"
    if page and re.search(r"applications? (?:are |is |have )?(?:closed|ended)|no longer accepting applications|this (?:job|position) (?:is |has been )?(?:closed|filled)",text,re.I):status="closed"
    elif page and re.search(r"register for future|future internship opportunities|expression of interest",title,re.I):status="future"
    checked=page.snapshot.checked_at if page else utc_now()
    provenance="posting metadata" if page else "public ATS feed" if lead.via=="feed" else "browser observation" if lead.via=="agent" else "search-result lead"
    level="internship" if re.search(r"intern|co[- ]?op|trainee",title,re.I) else "experienced" if re.search(r"\b(?:senior|staff|principal|manager|director|lead)\b",title,re.I) else "new_grad" if re.search(r"new[- ]?grad|graduate",title,re.I) else "entry_level" if re.search(r"entry[- ]?level|junior",title,re.I) else "unknown"
    description=""
    if page:
        lines=[line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
        description=next((line for line in lines if re.search(r"software|robotics?|engineer|research|programming|interns?",line,re.I)),"")[:350]
    listing = DiscoveryListing(id=listing_id(url,cycle),title=title[:160],organization=organization[:120],
        kind=kind,locations=locations,seniority=level,
        cycle=cycle,call_status=status,apply_url=url,source_url=page.snapshot.url if page else lead.source_url or url,
        checked_at=checked,found_via=lead.via,verification="partial" if page or lead.via=="feed" else "uncertain",
        summary=(lead.snippet or "")[:350] if not page else description or "Source posting retrieved. Detailed requirements are checked only when you select this target.",
        reasons=[f"Retrieved {provenance}; not an eligibility decision.","Visa, funding and application requirements remain unknown until checked.",
                 "Detailed preparation extraction has not run yet."],
    )
    return source_filter_evidence(listing, page)


class BasicDiscoveryEngine:
    def __init__(self,settings,ledger: DiscoveryState,*,web=None,browser=None,follow_agent_links=False):
        self.settings=settings;self.ledger=ledger
        self.web=web or DiscoveryWebClient(settings)
        self.browser=browser or BrowserFallback(settings)
        self.follow_agent_links=follow_agent_links

    def run(self,preferences: DiscoveryPreferences,*,previous=None,previous_pages=None,on_event=None,on_progress=None) -> EngineResult:
        result=EngineResult(usage={"searches":0,"fetch_urls":0,"extractions":0,"match_calls":0,"agent_runs":0,"ai_attempts":0})
        deadline=time.monotonic()+getattr(self.settings,"discovery_basic_seconds",90)
        candidates={};pages={};seen=set();boards={};leads={};browser_targets={};fatal=False
        def event(stage,message,url=""):
            e=RunEvent(stage=stage,message=message,url=url,timestamp=utc_now())
            result.events.append(e)
            if on_event:on_event(e)
        def warning(message,url=""):
            result.errors.append(message);result.partial=True;event("warning",message,url)
        def update():
            # No Groq request is allowed in the basic finder, even if configured.
            result.listings=rank_listings(preferences,list(candidates.values()),settings=None)
            if preferences.locations:
                result.listings.sort(key=lambda listing:(not any(place_matches(place,location) for place in preferences.locations for location in listing.locations),
                    bool(listing.locations),-listing.score))
            for listing in result.listings:
                original=candidates.get(listing.id)
                listing.reasons=list(dict.fromkeys([*(original.reasons if original else []),
                    *[reason.replace("Heuristic fallback: Groq API key is not configured.","Deterministic preference ranking; no AI requested.") for reason in listing.reasons]]))
            result.listings.extend(v for v in candidates.values() if v.call_status=="closed")
            result.listings=[classify_constraints(v,preferences) for v in result.listings]
            result.pages=list(pages.values())
            if on_progress:on_progress(result.model_copy(deep=True))
        def add(listing):
            if listing and "internship" in preferences.seniority and not any(level in preferences.seniority for level in ["experienced","entry_level","new_grad"]) and listing.kind=="job" and listing.seniority!="internship":
                return
            if listing and role_relevance(preferences,listing.title,listing.summary)>0:
                old=candidates.get(listing.id)
                old=old or next((v for v in candidates.values() if canonical_url(v.apply_url)==canonical_url(listing.apply_url) and v.locations),None)
                if old and old.locations and not listing.locations:
                    listing.locations=list(old.locations)
                if old is None or listing.verification=="partial":candidates[listing.id]=listing
                if listing.cycle!="unknown" and listing.verification=="partial":
                    for identifier,value in list(candidates.items()):
                        if identifier!=listing.id and value.cycle=="unknown" and canonical_url(value.apply_url)==canonical_url(listing.apply_url):
                            del candidates[identifier]
        def read(urls):
            nonlocal fatal
            selected=[u for u in dict.fromkeys(urls) if canonical_url(u) and u not in seen][:max(0,45-result.usage["fetch_urls"])]
            outcomes=[]
            for i in range(0,len(selected),10):
                batch=selected[i:i+10]
                if fatal or time.monotonic()>=deadline:break
                if not self.ledger.reserve("fetch_urls",len(batch),self.settings.discovery_daily_fetch_urls) or not self.ledger.reserve("fetch_minute",len(batch),120,window=60):
                    warning("Fetch allowance reached; retrieved leads remain visible.");break
                seen.update(batch);result.usage["fetch_urls"]+=len(batch)
                try:
                    fetched,errors=self.web.fetch(batch,format="markdown",ttl=3600)
                except ProviderError as exc:
                    warning(str(exc));fatal=exc.status in {"HTTP_401","HTTP_402","HTTP_403"};continue
                for url,message in errors.items():
                    warning(message,url)
                    lead=leads.get(canonical_url(url))
                    if lead and lead.kind!='posting':
                        company=_named_company(lead,preferences.companies)
                        if company:browser_targets.setdefault(company,lead.model_copy(update={'organization':company}))
                for page in fetched:
                    key=canonical_url(page.requested_url)
                    pages[(page.snapshot.url,page.snapshot.content_hash)]=page
                    outcomes.append((key,page));event("fetch","Read public source; no AI extraction required for discovery.",page.snapshot.url)
            return outcomes
        event("plan","Find first: Search and source metadata. No LLM dependency; detail extraction follows target selection.")
        tasks=plan_searches(preferences)[:12]
        with ThreadPoolExecutor(max_workers=4) as pool:
            for offset in range(0,len(tasks),4):
                if fatal or time.monotonic()>=deadline:break
                futures=[]
                for task in tasks[offset:offset+4]:
                    if not self.ledger.reserve("searches",1,self.settings.discovery_daily_searches) or not self.ledger.reserve("search_minute",1,25,window=60):
                        warning("Search allowance reached.");break
                    result.usage["searches"]+=1;futures.append((task,pool.submit(self.web.search,task)))
                for task,future in futures:
                    try:found=future.result()
                    except ProviderError as exc:
                        warning(str(exc));fatal=exc.status in {"HTTP_401","HTTP_402","HTTP_403"};continue
                    event("search",f'{task.label}: "{task.query}" → {len(found)} source links.')
                    for raw in found:
                        lead=classify_url(_application_url(raw.url))
                        if not lead:continue
                        lead.title=raw.title;lead.snippet=raw.snippet;lead.intent=task.intent
                        lead.organization=(_named_company(lead,[task.company]) if task.company else None) or lead.organization
                        if lead.kind=="board":boards.setdefault(lead.url,lead)
                        else:leads.setdefault(lead.url,lead)
                        add(source_listing(lead))
                update()
        event("collect",f"Found {len(leads)} page/posting leads and {len(boards)} ATS boards; cards do not wait for AI.")
        # Public feeds supply titles/locations even when arbitrary page parsing fails.
        feed_refs={}
        for lead in sorted(boards.values(),key=lambda l:_lead_priority(preferences,l))[:6]:
            ref=detect_ats(lead.url)
            if ref and not ref.readable:
                company=_named_company(lead,preferences.companies)
                if company:browser_targets[company]=lead.model_copy(update={"organization":company})
            elif ref and ref.feed_url:feed_refs[ref.feed_url]=(ref,lead)
            else:leads.setdefault(lead.url,lead)
        for key,page in read(list(feed_refs)):
            if key not in feed_refs:continue
            ref,board=feed_refs[key]
            rows=parse_feed(ref,page)
            if rows is None:
                warning("Public ATS feed was not readable; retained direct leads and scheduled board links.",page.snapshot.url)
                leads.setdefault(board.url,board);continue
            for lead in sorted(rows,key=lambda l:_lead_priority(preferences,l)):
                if role_relevance(preferences,lead.title,lead.description or "")<=0:continue
                metadata=source_listing(lead,lead.evidence_page)
                if metadata is None or (preferences.seniority==["internship"] and metadata.kind=="job" and metadata.seniority!="internship"):continue
                lead.kind="posting";leads[lead.url]=lead
                if lead.evidence_page:pages[(lead.evidence_page.snapshot.url,lead.evidence_page.snapshot.content_hash)]=lead.evidence_page
                add(metadata)
            event("feed",f"Read {len(rows)} actual feed rows; titles and locations available without Groq.",page.snapshot.url)
        update()
        # Individual postings and program sources: deterministic metadata only.
        ordered=sorted(leads.values(),key=lambda l:_lead_priority(preferences,l))
        for wave in range(2):
            chosen={lead.url:lead for lead in ordered if lead.url not in seen}
            if not chosen or time.monotonic()>=deadline:break
            for key,page in read(list(chosen)[:12 if wave==0 else 8]):
                lead=chosen.get(key)
                if not lead:continue
                try:adapted=[o for o in parse_snapshot(page.snapshot) if not o.id.startswith("source-")]
                except (ValueError,TypeError,IndexError):adapted=[]
                if adapted:
                    for target in adapted:
                        add(source_filter_evidence(DiscoveryListing(id=listing_id(target.source_url,target.cycle),title=target.program,organization=target.program,
                            kind="program" if target.category=="Research" else "job",seniority="internship",cycle=target.cycle,
                            locations=[target.country] if target.country!="Unknown" else [],call_status=target.call_status,
                            requirements=target.facts,source_url=target.source_url,apply_url=target.source_url,checked_at=target.checked_at,
                            verification=target.verification,summary=target.summary,reasons=["Reviewed source adapter; unknowns remain visible."]),page))
                else:add(source_listing(lead,page))
                for following in posting_links(page):
                    following.intent=lead.intent;leads.setdefault(following.url,following)
            update();ordered=sorted(leads.values(),key=lambda l:_lead_priority(preferences,l))
        # Preserve automatic portal capability, but never exceed the authorized total.
        def agent_openings(rows):
            observed=[SourceLead.model_validate(row) if isinstance(row,dict) else row for row in rows]
            for row in observed:
                row.kind="posting";row.via="agent"
                add(source_listing(row))
            update()
            if self.follow_agent_links and observed:
                by_url={canonical_url(row.url):row for row in observed}
                for key,page in read([row.url for row in observed]):
                    row=by_url.get(key)
                    if row:
                        for identifier,value in list(candidates.items()):
                            if canonical_url(value.apply_url)==canonical_url(row.url):
                                # A new page observation supersedes cached link-only metadata.
                                candidates.pop(identifier)
                        add(source_listing(row,page))
                update()
        for company,lead in list(browser_targets.items())[:2]:
            key="agent:"+self.browser.cache_key(lead,preferences)
            cached=self.ledger.cached(key)
            if cached is not None:
                for row in cached:
                    listing=source_listing(SourceLead.model_validate(row))
                    if listing:
                        listing.checked_at=self.ledger.cache_observed_at(key,86400) or listing.checked_at
                        listing.reasons.insert(0,"Cached browser observation; not checked again in this run.")
                        add(listing)
                if self.follow_agent_links:agent_openings(cached)
                event("agent",f"Used cached browser observations for {company}; no new paid run.",lead.url);continue
            pending_key="pending:"+key
            if self.ledger.cached(pending_key) is not None:
                warning("An earlier Agent run needs status reconciliation; no duplicate start.",lead.url);continue
            steps=self.settings.tinyfish_agent_max_steps
            verified=type(steps)is int and ((self.settings.tinyfish_agent_step_cap_verified and 1<=steps<=500) or (self.settings.tinyfish_agent_default_cap_verified and steps==150))
            if not self.settings.tinyfish_agent_enabled or not verified:
                warning("Portal requires browser Agent, which is not enabled with a verified budget.",lead.url);continue
            rate=self.settings.tinyfish_agent_step_cost_usd
            if not math.isfinite(rate) or rate<=0:warning("Agent price is not verified.",lead.url);continue
            maximum=steps*rate
            if not self.ledger.acquire(pending_key,{"run_id":None,"lead":lead.model_dump()},10**9):continue
            completed=self.ledger.cached(key)
            if completed is not None:
                self.ledger.delete_cache(pending_key)
                for row in completed:
                    listing=source_listing(SourceLead.model_validate(row))
                    if listing:
                        listing.checked_at=self.ledger.cache_observed_at(key,86400) or listing.checked_at
                        add(listing)
                if self.follow_agent_links:agent_openings(completed)
                continue
            if time.monotonic()>=deadline or not self.ledger.reserve("agent_session_usd",maximum,self.settings.discovery_agent_budget_usd,window=10**15):
                self.ledger.delete_cache(pending_key)
                warning("Authorized Agent budget is reserved/exhausted or reading deadline reached; no additional browser run.",lead.url);continue
            try:
                def started(run_id):self.ledger.cache(pending_key,{"run_id":run_id,"lead":lead.model_dump()},10**9)
                result.usage["agent_runs"]+=1
                openings=self.browser.find(lead,preferences,on_started=started)
                self.ledger.cache(key,[o.model_dump() for o in openings],86400);self.ledger.delete_cache(pending_key)
                agent_openings(openings)
                event("agent",f"Browser returned {len(openings)} observed posting links.",lead.url)
            except ProviderError as exc:
                self.ledger.cache(pending_key,{"run_id":exc.run_id,"lead":lead.model_dump()},10**9);warning(str(exc),lead.url)
        for old in previous or []:
            if old.id not in candidates:
                candidates[old.id]=_uncertain(old,"Earlier source observation not revalidated; not a fresh result.")
        # Preserve prior source records so old selected targets keep attributable history.
        for page in previous_pages or []:pages.setdefault((page.snapshot.url,page.snapshot.content_hash),page)
        update()
        event("extract","Detailed AI extraction intentionally deferred until you select preparation targets.")
        event("match",f"Filtered/ranked {len(result.listings)} source-backed leads using deterministic role/place rules; zero LLM calls.")
        if time.monotonic()>=deadline:warning("Discovery reading deadline reached; retrieved leads remain available.")
        if not result.listings and result.errors:result.usage["failed"]=1
        result.errors=list(dict.fromkeys(result.errors))
        event("done","Shortlist available; missing details stay unknown." if result.listings else "No matching leads found; inspect source gaps rather than assuming no internships exist.")
        return result
