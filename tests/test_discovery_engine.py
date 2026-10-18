from __future__ import annotations

import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from app.config import settings
from app.discovery.contracts import DiscoveryListing, DiscoveryPreferences, ExtractionResult, RunBudget, SearchTask, SourceLead, WebPage
from app.discovery.engine import DiscoveryEngine
from app.discovery.provider import ProviderError
from app.discovery.ranking import rank_listings
from app.discovery.state import DiscoveryState
from app.models import Fact, SourceSnapshot


URL = "https://careers.example.org/jobs/1001/software-engineer-intern"


def page(url=URL, text="# Software Engineer Intern\n## Basic Qualifications\nKnowledge of Python and algorithms required."):
    return WebPage(snapshot=SourceSnapshot(id="source-test",url=url,title="Software Engineer Intern",text=text,
                                          content_hash=hashlib.sha256(text.encode()).hexdigest()),requested_url=url)


class Web:
    def __init__(self, pages, leads=None):
        self.pages={p.requested_url:p for p in pages}
        self.leads=leads or [SourceLead(url=URL,title="Software Engineer Intern",organization="Example")]
        self.searches=[]
        self.reads=[]

    def search(self, task):
        self.searches.append(task)
        return self.leads

    def fetch(self, urls, format="markdown", ttl=0):
        self.reads.extend(urls)
        return [self.pages[u] for u in urls if u in self.pages],{u:"Source unavailable" for u in urls if u not in self.pages}


class Extractor:
    def __init__(self):
        self.calls=[]

    def extract(self,p,prefs,lead,remaining_seconds=None):
        self.calls.append(p.snapshot.url)
        if "careers page" in p.snapshot.text:
            return ExtractionResult(page_type="index",leads=[SourceLead(url=URL,kind="posting",via="link")])
        return ExtractionResult(page_type="posting",listings=[DiscoveryListing(
            title="Software Engineer Intern",organization="Example",seniority="internship",
            summary="Build software with Python and algorithms",locations=["Germany"],
            apply_url=p.snapshot.url,source_url=p.snapshot.url,checked_at=p.snapshot.checked_at,
            requirements=[Fact(name="skills",value=["Python","algorithms"],kind="requirement",status="known",
                               excerpt="Knowledge of Python and algorithms required.",source_url=p.snapshot.url,source_id=p.snapshot.id)],
        )])


class Browser:
    def cache_key(self,lead,prefs):
        return "test-browser-key"

    def find(self,lead,prefs):
        raise AssertionError("Metered browser must not run without a verified hard cap")


def engine(tmp_path,web,extractor=None,*,ledger=None,browser=None,ranking=None,**config):
    values=dict(discovery_state_path=str(tmp_path/"state.sqlite"),groq_key="",
                tinyfish_agent_enabled=False,tinyfish_agent_step_cap_verified=False)
    values.update(config)
    conf=replace(settings,**values)
    ledger=ledger or DiscoveryState(conf.discovery_state_path)
    return DiscoveryEngine(conf,ledger,web=web,extractor=extractor or Extractor(),browser=browser or Browser(),ranking=ranking or rank_listings)


def test_novel_posting_search_to_extraction_ranked_without_main_graph(tmp_path):
    web=Web([page()]);extractor=Extractor()
    result=engine(tmp_path,web,extractor).run(DiscoveryPreferences(roles=["software engineer"],locations=["Germany"],opportunity_types=["company_roles"]))
    assert result.listings and result.listings[0].requirements[0].value==["Python","algorithms"]
    assert result.listings[0].score>60
    assert len(web.reads)==1 and len(extractor.calls)==1
    assert {e.stage for e in result.events}>={"plan","search","fetch","extract","match","done"}
    assert "Heuristic fallback" in " ".join(result.listings[0].reasons)


def test_index_leads_followed_to_specific_posting(tmp_path):
    board="https://careers.example.org/careers"
    web=Web([page(board,"# careers page"),page()],[SourceLead(url=board)])
    result=engine(tmp_path,web).run(DiscoveryPreferences(roles=["software engineer"],opportunity_types=["company_roles"]))
    assert result.listings[0].apply_url==URL
    assert web.reads==[board,URL]


def test_named_ashby_portal_exposes_agent_gate_not_fake_empty_result(tmp_path):
    web=Web([], [SourceLead(url="https://jobs.ashbyhq.com/Example",organization="Example")])
    result=engine(tmp_path,web).run(DiscoveryPreferences(roles=["software engineer"],companies=["Example"],opportunity_types=["company_roles"]))
    assert not result.listings
    assert any("step/spend cap" in e for e in result.errors)
    assert result.usage["agent_runs"]==0


def test_authorized_agent_cache_used_without_new_metered_call(tmp_path):
    web=Web([page()],[SourceLead(url="https://jobs.ashbyhq.com/Example",organization="Example")])
    runner=engine(tmp_path,web)
    runner.ledger.cache("agent:test-browser-key",[SourceLead(url=URL,kind="posting",via="agent").model_dump()],86400)
    result=runner.run(DiscoveryPreferences(roles=["software engineer"],companies=["Example"],opportunity_types=["company_roles"]))
    assert result.listings and result.usage["agent_runs"]==0
    assert any("cached Agent" in e.message for e in result.events)


def test_ai_extraction_cache_avoids_same_source_repeat(tmp_path):
    extractor=Extractor();runner=engine(tmp_path,Web([page()]),extractor)
    prefs=DiscoveryPreferences(roles=["software engineer"],opportunity_types=["company_roles"])
    first=runner.run(prefs);second=runner.run(prefs)
    assert first.listings and second.listings
    assert len(extractor.calls)==1
    assert second.usage["extractions"]==0


def test_daily_ai_budget_skip_visible_and_no_extractor_request(tmp_path):
    extractor=Extractor();runner=engine(tmp_path,Web([page()]),extractor,discovery_daily_ai_calls=0)
    result=runner.run(DiscoveryPreferences(roles=["software engineer"],opportunity_types=["company_roles"]))
    assert not extractor.calls
    assert result.partial and any("extraction skipped" in error for error in result.errors)


def test_terminal_provider_auth_failure_does_not_retry_queries(tmp_path):
    class Failing(Web):
        def search(self,task):
            self.searches.append(task)
            raise ProviderError("TinyFish authentication failed",status="HTTP_401")
    web=Failing([])
    result=engine(tmp_path,web).run(DiscoveryPreferences(roles=["software engineer"]))
    assert 1 <= len(web.searches) <= 4 and result.partial
    assert len({task.query for task in web.searches}) == len(web.searches)
    assert not web.reads


def test_zero_run_limits_make_no_provider_requests(tmp_path):
    web=Web([page()])
    result=engine(tmp_path,web).run(DiscoveryPreferences(roles=["software engineer"]),budget=RunBudget(max_searches=0,max_fetch_urls=0,max_extractions=0))
    assert web.searches==[] and web.reads==[] and result.listings==[]


PREFS = DiscoveryPreferences(roles=["software engineering intern"], opportunity_types=["company_roles"])
PORTAL = SourceLead(url="https://jobs.ashbyhq.com/Example", organization="Example")
AGENT_PREFS = PREFS.model_copy(update={"companies": ["Example"]})
AGENT_CONFIG = dict(tinyfish_agent_enabled=True, tinyfish_agent_step_cap_verified=True,
                    tinyfish_agent_max_steps=10, discovery_agent_budget_usd=3)


def listing(url=URL, **changes):
    values=dict(id="prior-listing", title="Software Engineer Intern", organization="Example",
                seniority="internship", apply_url=url, source_url=url,
                checked_at="2026-10-16T12:00:00+00:00", call_status="open",
                requirements=[Fact(name="skills", value=["Python"], status="known", kind="requirement",
                                   excerpt="Python required.", source_url=url, source_id="source-old", version_id="skills@1")])
    values.update(changes)
    return DiscoveryListing(**values)


class Outputs:
    def __init__(self, outputs):
        self.outputs=outputs
        self.calls=[]

    def extract(self, page, preferences, lead, remaining_seconds=None):
        self.calls.append((page.snapshot.url, remaining_seconds))
        return self.outputs[page.snapshot.url].model_copy(deep=True)


class MemoryLedger:
    """Atomic ledger contract fake; no provider or shared runtime database access."""
    def __init__(self):
        self.values={}
        self.reservations=[]
        self.lock=threading.Lock()

    def cached(self, key):
        with self.lock:
            return self.values.get(key)

    def cache(self, key, value, seconds):
        with self.lock:
            self.values[key]=value

    def acquire(self, key, value, seconds):
        with self.lock:
            if key in self.values:
                return False
            self.values[key]=value
            return True

    def delete_cache(self, key):
        with self.lock:
            self.values.pop(key, None)

    def reserve(self, key, amount, cap, **kwargs):
        with self.lock:
            total=sum(value for name, value in self.reservations if name==key)
            if total+amount>cap:
                return False
            self.reservations.append((key, amount))
            return True


class AgentBrowser(Browser):
    def __init__(self, failure=None, openings=None, recovery=None):
        self.failure=failure
        self.openings=openings or []
        self.recovery=recovery
        self.finds=0
        self.polls=[]

    def find(self, lead, prefs, remaining_seconds=None):
        self.finds+=1
        if self.failure:
            raise self.failure
        return self.openings

    def recover(self, run_id, lead, remaining_seconds=None):
        self.polls.append(run_id)
        if isinstance(self.recovery, Exception):
            raise self.recovery
        return self.recovery or []


@pytest.mark.parametrize("posting_first", [False, True])
def test_specific_posting_wins_over_richer_index_in_either_order(tmp_path, posting_first):
    board="https://careers.example.org/careers"
    index=listing(source_url=board, cycle=" Summer--2027 ", requirements=[
        Fact(name=f"fact_{i}", value="Python", status="known", excerpt="Python required.") for i in range(20)])
    final=listing(cycle="summer 2027", summary="Specific posting")
    outputs=Outputs({board: ExtractionResult(page_type="index", listings=[index]),
                     URL: ExtractionResult(page_type="posting", listings=[final])})
    leads=[SourceLead(url=URL, title=final.title), SourceLead(url=board)] if posting_first else [SourceLead(url=board)]
    result=engine(tmp_path, Web([page(board), page()], leads), outputs).run(PREFS)
    assert len(result.listings)==1
    assert result.listings[0].source_url==URL
    assert result.listings[0].requirements[0].status=="known"
    assert len(result.listings[0].requirements)==1
    assert not any("Index summary retained" in error for error in result.errors)


def test_unfetched_index_is_explicitly_uncertain_with_only_prior_quotes(tmp_path):
    board="https://careers.example.org/careers"
    index=listing(source_url=board)
    outputs=Outputs({board: ExtractionResult(page_type="index", listings=[index])})
    result=engine(tmp_path, Web([page(board)], [SourceLead(url=board)]), outputs).run(PREFS)
    row=result.listings[0]
    assert result.partial and row.verification=="uncertain" and row.call_status=="unknown"
    assert row.summary.startswith("INDEX SUMMARY ONLY")
    assert row.requirements[0].status=="unknown" and row.requirements[0].value is None
    assert row.requirements[0].excerpt=="Python required."
    assert "Index-only summary" in " ".join(row.reasons)


def test_unknown_index_identity_does_not_duplicate_identified_posting(tmp_path):
    board="https://careers.example.org/careers"
    outputs=Outputs({board: ExtractionResult(page_type="index", listings=[listing(source_url=board)]),
                     URL: ExtractionResult(page_type="posting", listings=[listing(cycle="Summer 2027")])})
    result=engine(tmp_path, Web([page(board), page()], [SourceLead(url=board)]), outputs).run(PREFS)
    assert len(result.listings)==1 and result.listings[0].cycle=="Summer 2027"


def test_late_unknown_index_cannot_duplicate_final_cohort(tmp_path):
    board="https://careers.example.org/careers"
    outputs=Outputs({board: ExtractionResult(page_type="index", listings=[listing(source_url=board)]),
                     URL: ExtractionResult(page_type="posting", listings=[listing(cycle="Summer 2027")])})
    result=engine(tmp_path, Web([page(), page(board)], [SourceLead(url=URL), SourceLead(url=board)]), outputs).run(PREFS)
    assert len(result.listings)==1 and result.listings[0].cycle=="Summer 2027"


def test_canonical_cycle_identity_preserves_distinct_cohorts(tmp_path):
    outputs=Outputs({URL: ExtractionResult(page_type="posting", listings=[
        listing(cycle=" Summer--2027 "), listing(cycle="summer 2027"), listing(cycle="Fall 2027")])})
    result=engine(tmp_path, Web([page()]), outputs).run(PREFS)
    assert len(result.listings)==2
    assert len({row.id for row in result.listings})==2
    again=engine(tmp_path, Web([page()]), Outputs({URL: ExtractionResult(page_type="posting", listings=[listing(cycle="SUMMER 2027")])})).run(PREFS)
    assert again.listings[0].id==next(row.id for row in result.listings if row.cycle=="summer 2027")


def test_all_prior_listings_and_pages_survive_zero_coverage_without_mutation(tmp_path):
    previous=[listing(url=f"https://careers.example.org/jobs/{i+1000}", id=f"old-{i}", saved=True,
                      hidden=i%2==0, cycle="2027", funding_level="paid", visa_status="sponsors",
                      reasons=["Sponsors visa"]) for i in range(9)]
    snapshots=[page(row.source_url) for row in previous]
    result=engine(tmp_path, Web([])).run(PREFS, previous=previous, previous_pages=snapshots,
                                        budget=RunBudget(max_searches=0, max_fetch_urls=0, max_rechecks=0))
    assert len(result.listings)==len(result.pages)==9
    assert {row.id for row in result.listings}=={row.id for row in previous}
    for old, retained in zip(previous, result.listings, strict=True):
        assert retained.checked_at==old.checked_at and retained.saved==old.saved and retained.hidden==old.hidden
        assert retained.verification=="uncertain" and retained.call_status=="unknown"
        assert retained.funding_level==retained.visa_status=="unknown"
        assert retained.requirements[0].status=="unknown" and retained.requirements[0].value is None
        assert retained.requirements[0].excerpt==old.requirements[0].excerpt
        assert retained.requirements[0].version_id==old.requirements[0].version_id
        assert old.requirements[0].status=="known" and old.call_status=="open"
        assert "Prior (not current): Sponsors visa" in retained.reasons
    assert result.partial


def test_missing_cohort_remains_uncertain_even_when_same_source_was_fetched(tmp_path):
    old=listing(cycle="Spring 2027", saved=True)
    outputs=Outputs({URL: ExtractionResult(page_type="posting", listings=[listing(cycle="Fall 2027")])})
    result=engine(tmp_path, Web([page()]), outputs).run(PREFS, previous=[old], previous_pages=[page()])
    prior=next(row for row in result.listings if row.cycle=="Spring 2027")
    assert prior.id==old.id and prior.verification=="uncertain"
    assert prior.requirements[0].status=="unknown"


def test_closed_observation_survives_ranking_and_prior_closed_is_not_reopened(tmp_path):
    outputs=Outputs({URL: ExtractionResult(page_type="closed", listings=[listing()])})
    result=engine(tmp_path, Web([page()]), outputs).run(PREFS)
    assert len(result.listings)==1 and result.listings[0].call_status=="closed"
    assert result.listings[0].score==0
    assert "not an active match" in result.listings[0].reasons[0]
    retained=engine(tmp_path, Web([])).run(PREFS, previous=result.listings,
                                         budget=RunBudget(max_searches=0, max_rechecks=0))
    assert retained.listings[0].call_status=="closed" and retained.listings[0].verification=="uncertain"


def test_closed_final_observation_beats_richer_open_final_observation(tmp_path):
    second="https://careers.example.org/jobs/1002"
    outputs=Outputs({URL: ExtractionResult(page_type="posting", listings=[listing()]),
                     second: ExtractionResult(page_type="closed", listings=[listing(requirements=[])])})
    result=engine(tmp_path, Web([page(), page(second)], [SourceLead(url=URL), SourceLead(url=second)]), outputs).run(PREFS)
    assert len(result.listings)==1 and result.listings[0].call_status=="closed"


def test_closed_index_does_not_declare_individual_posting_closed(tmp_path):
    board="https://careers.example.org/careers"
    outputs=Outputs({board: ExtractionResult(page_type="index", listings=[listing(source_url=board, call_status="closed")])})
    result=engine(tmp_path, Web([page(board)], [SourceLead(url=board)]), outputs).run(PREFS)
    assert result.listings[0].call_status=="unknown" and result.listings[0].verification=="uncertain"


def test_feed_selection_uses_role_stems_and_requested_seniority_before_row_limit(tmp_path):
    board="https://job-boards.greenhouse.io/example"
    feed="https://boards-api.greenhouse.io/v1/boards/example/jobs"
    target=board+"/jobs/9999"
    jobs=[{"id": i+1000, "title": "Senior Software Engineer"} for i in range(6)]
    jobs.extend({"id": i+2000, "title": "Marketing Intern"} for i in range(6))
    jobs.append({"id": 9999, "title": "Software Engineer Intern"})
    feed_page=page(feed)
    feed_page.json_body={"jobs": jobs}
    web=Web([feed_page, page(target)], [SourceLead(url=board)])
    result=engine(tmp_path, web).run(PREFS, budget=RunBudget(max_postings_per_board=1))
    assert web.reads==[feed, target]
    assert result.listings and not result.partial  # Clear misfits aren't a coverage ceiling.


def test_canonical_dedup_precedes_second_wave_slice(tmp_path):
    board="https://careers.example.org/careers"
    repeated=[SourceLead(url=URL+("?utm_source=scout" if i%2 else "/"), kind="posting") for i in range(40)]
    outputs=Outputs({board: ExtractionResult(page_type="index", leads=repeated),
                     URL: ExtractionResult(page_type="posting", listings=[listing()])})
    web=Web([page(board), page()], [SourceLead(url=board)])
    result=engine(tmp_path, web, outputs).run(PREFS, budget=RunBudget(max_leads=1))
    assert web.reads==[board, URL] and result.listings


def test_seen_duplicate_leads_do_not_consume_third_wave_slots(tmp_path):
    board="https://careers.example.org/careers"
    second="https://careers.example.org/jobs/1002"
    outputs=Outputs({board: ExtractionResult(page_type="index", leads=[SourceLead(url=URL, kind="posting")]),
                     URL: ExtractionResult(page_type="posting", listings=[listing()], leads=[
                         *[SourceLead(url=URL, kind="posting") for _ in range(15)], SourceLead(url=second, kind="posting")]),
                     second: ExtractionResult(page_type="posting", listings=[listing(second)])})
    web=Web([page(board), page(), page(second)], [SourceLead(url=board)])
    result=engine(tmp_path, web, outputs).run(PREFS, budget=RunBudget(max_leads=1))
    assert web.reads==[board, URL, second] and len(result.listings)==2


def test_prior_cohorts_are_deduplicated_before_recheck_limit(tmp_path):
    other="https://careers.example.org/jobs/1002"
    previous=[listing(id=f"old-{i}", cycle=f"Cohort {i}") for i in range(8)]+[listing(other)]
    web=Web([page(), page(other)])
    engine(tmp_path, web).run(PREFS, previous=previous, budget=RunBudget(max_searches=0, max_rechecks=2))
    assert web.reads==[URL, other]


def test_parallel_search_terminal_failure_stops_after_initial_four(tmp_path, monkeypatch):
    tasks=[SearchTask(intent="web", query=f"query {i}", purpose="", label=str(i)) for i in range(12)]
    monkeypatch.setattr("app.discovery.engine.plan_searches", lambda prefs: tasks)
    class Failure(Web):
        def search(self, task):
            self.searches.append(task)
            raise ProviderError("Authentication failed", status="HTTP_401")
    web=Failure([])
    result=engine(tmp_path, web).run(PREFS)
    assert {task.query for task in web.searches}=={task.query for task in tasks[:4]}
    assert result.usage["searches"]==4 and result.partial and not web.reads


def test_search_concurrency_four_and_trace_preserves_query_plan_order(tmp_path, monkeypatch):
    tasks=[SearchTask(intent="web", query=f"query {i}", purpose="", label=str(i)) for i in range(12)]
    monkeypatch.setattr("app.discovery.engine.plan_searches", lambda prefs: tasks)
    barrier=threading.Barrier(4)
    class Parallel(Web):
        def __init__(self):
            super().__init__([])
            self.lock=threading.Lock()
            self.active=self.maximum=0
        def search(self, task):
            with self.lock:
                self.active+=1
                self.maximum=max(self.maximum, self.active)
                self.searches.append(task)
            barrier.wait(timeout=3)
            with self.lock:
                self.active-=1
            return []
    web=Parallel()
    result=engine(tmp_path, web).run(PREFS)
    assert web.maximum==4 and len(web.searches)==12
    assert [event.message.split(":")[0] for event in result.events if event.stage=="search"]==[str(i) for i in range(12)]


def test_daily_search_allowance_stops_dispatch_without_overshoot(tmp_path):
    web=Web([page()])
    result=engine(tmp_path, web, discovery_daily_searches=1).run(DiscoveryPreferences(roles=["software engineer"]))
    assert len(web.searches)==result.usage["searches"]==1
    assert any("Search allowance" in error for error in result.errors)


def test_extraction_checks_remaining_time_between_pages_in_same_batch(tmp_path, monkeypatch):
    clock=[0.0]
    monkeypatch.setattr("app.discovery.engine.time.monotonic", lambda: clock[0])
    other="https://careers.example.org/jobs/1002"
    class Slow(Extractor):
        def extract(self, p, prefs, lead, remaining_seconds=None):
            assert 0 < remaining_seconds <= 1
            result=super().extract(p, prefs, lead)
            clock[0]=2
            return result
    extractor=Slow()
    result=engine(tmp_path, Web([page(), page(other)], [SourceLead(url=URL), SourceLead(url=other)]), extractor).run(
        PREFS, budget=RunBudget(soft_deadline_ms=1000, hard_deadline_ms=1000))
    assert len(extractor.calls)==1 and len(result.pages)==2
    assert result.partial and result.usage["extractions"]==1 and result.usage["match_calls"]==0


def test_matching_checks_deadline_between_twenty_listing_batches(tmp_path, monkeypatch):
    clock=[0.0]
    monkeypatch.setattr("app.discovery.engine.time.monotonic", lambda: clock[0])
    outputs=Outputs({URL: ExtractionResult(page_type="posting", listings=[
        listing(f"https://careers.example.org/jobs/{i+1000}") for i in range(21)])})
    calls=[]
    def slow_rank(prefs, rows, settings=None, remaining_seconds=None):
        calls.append((len(rows), settings is not None, remaining_seconds))
        clock[0]=2
        return [row.model_copy(update={"score": 50}) for row in rows]
    result=engine(tmp_path, Web([page()]), outputs, ranking=slow_rank, groq_key="fake-key").run(
        PREFS, budget=RunBudget(soft_deadline_ms=1000, hard_deadline_ms=1000))
    assert calls==[(20, True, 1.0), (1, False, 0.0)]
    assert result.usage["match_calls"]==1 and result.partial


def test_matching_persistent_quota_stops_after_two_independent_failures(tmp_path):
    outputs=Outputs({URL: ExtractionResult(page_type="posting", listings=[
        listing(f"https://careers.example.org/jobs/{i+1000}") for i in range(41)])})
    calls=[]
    def failing_rank(prefs, rows, settings=None, remaining_seconds=None):
        calls.append(settings is not None)
        return [row.model_copy(update={"reasons": ["Heuristic fallback: Groq quota/rate limit reached."]}) for row in rows]
    result=engine(tmp_path, Web([page()]), outputs, ranking=failing_rank, groq_key="fake-key").run(PREFS)
    assert calls==[True, True, False] and result.usage["match_calls"]==2
    assert result.partial and any("AI matching failed" in error for error in result.errors)


def test_legacy_injected_extractor_supported_and_typeerror_is_not_retried(tmp_path):
    class Legacy(Extractor):
        def extract(self, p, prefs, lead):
            return super().extract(p, prefs, lead)
    assert engine(tmp_path, Web([page()]), Legacy()).run(PREFS).listings
    class Bug(Extractor):
        def extract(self, p, prefs, lead, remaining_seconds=None):
            self.calls.append(p.snapshot.url)
            raise TypeError("adapter bug")
    extractor=Bug()
    with pytest.raises(TypeError, match="adapter bug"):
        engine(tmp_path, Web([page()]), extractor).run(PREFS.model_copy(update={"keywords": ["different cache key"]}))
    assert extractor.calls==[URL]


def test_valid_empty_agent_cache_prevents_new_run_even_when_enabled(tmp_path):
    browser=AgentBrowser()
    ledger=MemoryLedger()
    ledger.cache("agent:test-browser-key", [], 86400)
    result=engine(tmp_path, Web([], [PORTAL]), ledger=ledger, browser=browser, **AGENT_CONFIG).run(AGENT_PREFS)
    assert browser.finds==0 and result.usage["agent_runs"]==0
    assert any("cached Agent" in event.message for event in result.events)


def test_unverified_step_cap_gates_enabled_agent_before_any_lease_or_charge(tmp_path):
    browser=AgentBrowser()
    ledger=MemoryLedger()
    config={**AGENT_CONFIG, "tinyfish_agent_step_cap_verified": False}
    result=engine(tmp_path, Web([], [PORTAL]), ledger=ledger, browser=browser, **config).run(AGENT_PREFS)
    assert browser.finds==0 and not ledger.values
    assert not any(name=="agent_session_usd" for name, amount in ledger.reservations)
    assert any("step/spend cap" in error for error in result.errors)


def test_unknown_agent_start_is_durable_and_never_automatically_retried(tmp_path):
    ledger=MemoryLedger()
    browser=AgentBrowser(failure=ProviderError("Connection lost", status="NETWORK_ERROR"))
    runner=engine(tmp_path, Web([], [PORTAL]), ledger=ledger, browser=browser, **AGENT_CONFIG)
    first=runner.run(AGENT_PREFS)
    second=runner.run(AGENT_PREFS)
    assert browser.finds==1 and browser.polls==[]
    assert first.usage["agent_runs"]==1 and second.usage["agent_runs"]==0
    assert ledger.cached("pending:agent:test-browser-key")["run_id"] is None
    assert sum(amount for name, amount in ledger.reservations if name=="agent_session_usd")==pytest.approx(0.16)
    assert any("No automatic resubmission" in error for error in second.errors)


def test_agent_run_id_is_recovered_once_per_later_run_without_repost(tmp_path):
    ledger=MemoryLedger()
    browser=AgentBrowser(failure=ProviderError("Stream timed out", run_id="run-123", status="TIMEOUT"),
                         recovery=ProviderError("Still running", run_id="run-123", status="RUNNING"))
    runner=engine(tmp_path, Web([page()], [PORTAL]), ledger=ledger, browser=browser, **AGENT_CONFIG)
    runner.run(AGENT_PREFS)
    runner.run(AGENT_PREFS)
    assert browser.finds==1 and browser.polls==["run-123"]
    assert ledger.cached("pending:agent:test-browser-key")
    browser.recovery=[SourceLead(url=URL, kind="posting", via="agent")]
    recovered=runner.run(AGENT_PREFS)
    assert recovered.listings and browser.finds==1 and browser.polls==["run-123", "run-123"]
    assert ledger.cached("pending:agent:test-browser-key") is None
    runner.run(AGENT_PREFS)
    assert browser.finds==1 and len(browser.polls)==2


def test_agent_started_id_persisted_before_stream_completion_and_recovered_after_error(tmp_path):
    ledger=MemoryLedger()
    class Started(AgentBrowser):
        def find(self, lead, prefs, *, on_started=None):
            self.finds+=1
            on_started("run-started")
            assert ledger.cached("pending:agent:test-browser-key")["run_id"]=="run-started"
            raise ProviderError("Stream lost", status="NETWORK_ERROR")
    browser=Started(recovery=[])
    runner=engine(tmp_path, Web([], [PORTAL]), ledger=ledger, browser=browser, **AGENT_CONFIG)
    runner.run(AGENT_PREFS)
    assert ledger.cached("pending:agent:test-browser-key")["run_id"]=="run-started"
    runner.run(AGENT_PREFS)
    assert browser.finds==1 and browser.polls==["run-started"]
    assert ledger.cached("agent:test-browser-key")==[]


def test_agent_goal_claim_is_atomic_between_simultaneous_hunts(tmp_path):
    ledger=MemoryLedger()
    started=threading.Event()
    release=threading.Event()
    class Blocking(AgentBrowser):
        def find(self, lead, prefs, remaining_seconds=None):
            self.finds+=1
            started.set()
            assert release.wait(3)
            return []
    browser=Blocking()
    first=engine(tmp_path, Web([], [PORTAL]), ledger=ledger, browser=browser, **AGENT_CONFIG)
    second=engine(tmp_path, Web([], [PORTAL]), ledger=ledger, browser=browser, **AGENT_CONFIG)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(first.run, AGENT_PREFS)
        assert started.wait(3)
        try:
            result=second.run(AGENT_PREFS)
            assert result.usage["agent_runs"]==0 and browser.finds==1
        finally:
            release.set()
        future.result(timeout=3)
    assert len([name for name, amount in ledger.reservations if name=="agent_session_usd"])==1
    assert ledger.cached("agent:test-browser-key")==[]


def test_existing_recovery_lease_prevents_duplicate_poll(tmp_path):
    ledger=MemoryLedger()
    ledger.cache("pending:agent:test-browser-key", {"run_id": "run-123", "lead": PORTAL.model_dump()}, 86400)
    ledger.cache("recovery:agent:test-browser-key", {"run_id": "run-123"}, 300)
    browser=AgentBrowser()
    result=engine(tmp_path, Web([], [PORTAL]), ledger=ledger, browser=browser, **AGENT_CONFIG).run(AGENT_PREFS)
    assert browser.finds==0 and not browser.polls and result.partial


def test_agent_budget_denial_releases_unstarted_goal_without_provider_call(tmp_path):
    ledger=MemoryLedger()
    browser=AgentBrowser()
    config={**AGENT_CONFIG, "discovery_agent_budget_usd": 0.1}
    result=engine(tmp_path, Web([], [PORTAL]), ledger=ledger, browser=browser, **config).run(AGENT_PREFS)
    assert browser.finds==0 and result.usage["agent_runs"]==0
    assert ledger.cached("pending:agent:test-browser-key") is None
    assert any("budget exhausted" in error for error in result.errors)


def test_agent_ashby_posting_links_are_fetched_instead_of_rerouted_to_board(tmp_path):
    posting="https://jobs.ashbyhq.com/Example/01234567-89ab-cdef-0123-456789abcdef"
    ledger=MemoryLedger()
    browser=AgentBrowser(openings=[SourceLead(url=posting, title="Software Engineer Intern", organization="Example", kind="posting", via="agent")])
    web=Web([page(posting)], [PORTAL])
    result=engine(tmp_path, web, ledger=ledger, browser=browser, **AGENT_CONFIG).run(AGENT_PREFS)
    assert web.reads==[posting] and browser.finds==1 and result.listings


def test_two_arbitrary_lever_sources_inline_without_posting_fetch_and_exact_feed_evidence(tmp_path):
    from app.discovery.urls import detect_ats
    boards = ["https://jobs.lever.co/orbital-dynamics", "https://jobs.eu.lever.co/lattice-research"]
    feeds = [detect_ats(board).feed_url for board in boards]
    urls = [f"{board}/12345678-1234-1234-1234-123456789abc" for board in boards]
    quote = "Knowledge of Python and algorithms required."
    pages = []
    for feed, url in zip(feeds, urls, strict=True):
        snapshot = page(feed, "Original JSON feed snapshot")
        snapshot.json_body = [{"text": "Software Engineer Intern", "hostedUrl": url,
            "descriptionPlain": "Build scientific software. " * 12,
            "lists": [{"text": "Basic Qualifications", "content": f"<li>{quote}</li>"}]}]
        pages.append(snapshot)
    class FeedExtractor(Extractor):
        def extract(self, p, prefs, lead, remaining_seconds=None):
            assert p.requested_url == lead.source_url == p.snapshot.url
            assert quote in p.snapshot.text and lead.description
            return super().extract(p, prefs, lead, remaining_seconds=remaining_seconds)
    extractor = FeedExtractor()
    web = Web(pages, [SourceLead(url=board) for board in boards])
    result = engine(tmp_path, web, extractor).run(PREFS)
    assert len(result.listings) == 2 and web.reads == feeds
    assert result.usage["fetch_urls"] == 2 and result.usage["extractions"] == 2
    assert {row.apply_url for row in result.listings} == set(urls)
    for row in result.listings:
        assert row.source_url in feeds and row.found_via == "feed"
        evidence = [p for p in result.pages if p.snapshot.url == row.source_url]
        assert len(evidence) == 2 and evidence[0].snapshot.text == "Original JSON feed snapshot"
        fact = row.requirements[0]
        assert fact.excerpt in evidence[-1].snapshot.text
        assert fact.source_id == evidence[-1].snapshot.id and fact.source_url == row.source_url


def test_short_lever_description_still_fetches_individual_posting(tmp_path):
    from app.discovery.urls import detect_ats
    board = "https://jobs.lever.co/orbital-dynamics"
    feed = detect_ats(board).feed_url
    target = board + "/12345678-1234-1234-1234-123456789abc"
    feed_page = page(feed)
    feed_page.json_body = [{"text": "Software Engineer Intern", "hostedUrl": target, "descriptionPlain": "Short summary."}]
    web = Web([feed_page, page(target)], [SourceLead(url=board)])
    result = engine(tmp_path, web).run(PREFS)
    assert web.reads == [feed, target] and result.listings[0].source_url == target


@pytest.mark.parametrize("slug", ["orbital-dynamics", "lattice-research"])
def test_feed_relevance_not_truncated_at_first_hundred_unrelated_rows(tmp_path, slug):
    board = f"https://job-boards.greenhouse.io/{slug}"
    feed = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    target = board + "/jobs/99001"
    feed_page = page(feed)
    feed_page.json_body = {"jobs": [{"id": i+1000, "title": "Marketing Intern"} for i in range(121)] + [
        {"id": 99001, "title": "Software Engineer Intern"}]}
    web = Web([feed_page, page(target)], [SourceLead(url=board)])
    result = engine(tmp_path, web).run(PREFS, budget=RunBudget(max_postings_per_board=1))
    assert web.reads == [feed, target] and result.listings
    assert not result.partial


def test_named_company_slug_not_provider_assigned_company_controls_agent(tmp_path):
    class ByGoalBrowser(AgentBrowser):
        def cache_key(self, lead, prefs):
            return lead.organization or "none"
    browser = ByGoalBrowser()
    leads = [SourceLead(url="https://jobs.ashbyhq.com/OtherEmployer", organization="Orbital Dynamics"),
             SourceLead(url="https://jobs.ashbyhq.com/orbitaldynamicsus", organization="Wrong search label")]
    ledger = MemoryLedger()
    ledger.cache("agent:Orbital Dynamics", [], 86400)
    result = engine(tmp_path, Web([], leads), ledger=ledger, browser=browser).run(
        PREFS.model_copy(update={"companies": ["Orbital Dynamics"]}))
    agent_urls = {e.url for e in result.events if e.stage == "agent"}
    assert agent_urls == {"https://jobs.ashbyhq.com/orbitaldynamicsus"}
    assert browser.finds == 0


def test_named_boards_first_then_search_hits_before_board_ceiling(tmp_path):
    from app.discovery.urls import detect_ats
    boards = ["https://jobs.lever.co/other-employer", "https://jobs.lever.co/orbitaldynamicsus"]
    feeds = [detect_ats(board).feed_url for board in boards]
    empty = page(feeds[1]); empty.json_body = []
    web = Web([empty], [*[SourceLead(url=boards[0]) for _ in range(8)], SourceLead(url=boards[1])])
    result = engine(tmp_path, web).run(PREFS.model_copy(update={"companies": ["Orbital Dynamics"]}), budget=RunBudget(max_boards=1))
    assert web.reads == [feeds[1]] and result.partial
    assert any("skipped" in e.message and e.url == boards[0] for e in result.events if e.stage == "source")


def test_open_web_selection_diverse_meaningful_and_relevant_before_fetch_cap(tmp_path, monkeypatch):
    tasks = [SearchTask(intent="web", query="open web", purpose="", label="web")]
    monkeypatch.setattr("app.discovery.engine.plan_searches", lambda prefs: tasks)
    senior = "https://careers.orbital.org/jobs/20001"
    wanted = "https://careers.lattice.org/jobs/80009"
    leads = [SourceLead(url="https://news.orbital.org/about", title="Company history"),
             SourceLead(url=senior, title="Senior Software Engineer"),
             SourceLead(url=wanted, title="Software Engineer Intern")]
    web = Web([page(wanted)], leads)
    result = engine(tmp_path, web).run(PREFS, budget=RunBudget(max_fetch_urls=1))
    assert web.reads == [wanted] and result.listings
    assert result.usage["pages_discovered"] == 0


def test_program_page_priority_precedes_web_and_limits_two_per_site(tmp_path, monkeypatch):
    tasks = [SearchTask(intent="web", query="web", purpose="", label="web"),
             SearchTask(intent="programs", query="research", purpose="", label="research")]
    monkeypatch.setattr("app.discovery.engine.plan_searches", lambda prefs: tasks)
    web_url = "https://careers.orbital.org/careers"
    programs = [f"https://lattice.edu/programs/summer-research-{i}" for i in range(4)]
    class PerTask(Web):
        def search(self, task):
            self.searches.append(task)
            return [SourceLead(url=web_url, title="Careers")] if task.intent == "web" else [SourceLead(url=url, title="Summer research internship") for url in programs]
    web = PerTask([page(programs[0]), page(programs[1])])
    result = engine(tmp_path, web).run(PREFS, budget=RunBudget(max_fetch_urls=2))
    assert web.reads == programs[:2] and result.usage["pages_discovered"] == 3


def test_posting_links_relevance_sorted_before_ten_lead_limit(tmp_path):
    board = "https://careers.orbital.org/careers"
    target = "https://careers.orbital.org/jobs/99001"
    text = "# Careers\n" + "\n".join(f"[Senior Software Engineer](/jobs/{i+10000})" for i in range(15)) + "\n[Software Engineer Intern](/jobs/99001)"
    outputs = Outputs({board: ExtractionResult(page_type="index"), target: ExtractionResult(page_type="posting", listings=[listing(target)])})
    web = Web([page(board, text), page(target)], [SourceLead(url=board)])
    result = engine(tmp_path, web, outputs).run(PREFS, budget=RunBudget(max_leads=1))
    assert web.reads == [board, target] and result.listings


def test_generic_category_never_becomes_selectable_even_with_injected_index_listing(tmp_path):
    category = "https://lattice.edu/internships"
    outputs = Outputs({category: ExtractionResult(page_type="index", listings=[listing(category, title="Internships")])})
    result = engine(tmp_path, Web([page(category)], [SourceLead(url=category)]), outputs).run(PREFS)
    assert not result.listings and result.usage["failed"] == 1
    assert any("category/index" in error for error in result.errors)


@pytest.mark.parametrize("warning", ["Groq output checked; unsupported evidence discarded.", "Groq response excerpt truncated; unobserved facts remain unknown.", "Groq returned invalid JSON or an invalid structured response; no retry was attempted."])
def test_benign_or_page_specific_groq_warning_does_not_stop_other_extractions(tmp_path, warning):
    other = "https://careers.lattice.org/jobs/80009"
    outputs = Outputs({URL: ExtractionResult(page_type="posting", listings=[listing()], warnings=[warning]),
                       other: ExtractionResult(page_type="posting", listings=[listing(other)])})
    result = engine(tmp_path, Web([page(), page(other)], [SourceLead(url=URL), SourceLead(url=other)]), outputs).run(PREFS)
    assert len(outputs.calls) == result.usage["extractions"] == 2 and len(result.listings) == 2


@pytest.mark.parametrize("message,expected", [("Groq authentication failed; check the server API key.", 1),
    ("Groq quota/rate limit reached; no retry was attempted.", 2)])
def test_fatal_or_persistent_quota_stops_only_uncached_ai_admissions(tmp_path, message, expected):
    urls = [f"https://careers.lattice.org/jobs/{i+90000}" for i in range(3)]
    outputs = Outputs({url: ExtractionResult(warnings=[message]) for url in urls})
    result = engine(tmp_path, Web([page(url) for url in urls], [SourceLead(url=url) for url in urls]), outputs).run(PREFS)
    assert len(outputs.calls) == expected and result.partial
    assert result.usage["failed"] == 1 and any(e.stage == "error" for e in result.events)


def test_one_transient_quota_does_not_discard_later_source(tmp_path):
    other = "https://careers.lattice.org/jobs/80009"
    outputs = Outputs({URL: ExtractionResult(warnings=["Groq quota/rate limit reached; no retry was attempted."]),
                       other: ExtractionResult(page_type="posting", listings=[listing(other)])})
    result = engine(tmp_path, Web([page(), page(other)], [SourceLead(url=URL), SourceLead(url=other)]), outputs).run(PREFS)
    assert len(outputs.calls) == 2 and result.listings[0].apply_url == other


def test_missing_fetch_outcome_is_source_failure_not_fake_success(tmp_path):
    class Missing(Web):
        def fetch(self, urls, **kwargs):
            self.reads.extend(urls)
            return [], {}
    result = engine(tmp_path, Missing([])).run(PREFS)
    assert result.partial and result.usage["failed"] == 1 and not result.listings
    assert any("no outcome" in error for error in result.errors)
    assert {e.stage for e in result.events} >= {"collect", "source", "agent", "recheck", "coverage", "error", "done"}


def test_refreshed_current_identity_preserves_saved_and_hidden_flags(tmp_path):
    previous = listing(saved=True, hidden=True)
    result = engine(tmp_path, Web([page()]), Outputs({URL: ExtractionResult(page_type="posting", listings=[listing(saved=False, hidden=False)])})).run(PREFS, previous=[previous])
    assert result.listings[0].saved and result.listings[0].hidden and result.listings[0].id == previous.id


def test_actual_cached_agent_observation_survives_posting_fetch_failure(tmp_path):
    ledger = MemoryLedger()
    ledger.cache("agent:test-browser-key", [SourceLead(url=URL, title="Software Engineer Intern", location="Berlin", organization="Example", kind="posting", via="agent", source_url=PORTAL.url).model_dump()], 86400)
    result = engine(tmp_path, Web([], [PORTAL]), ledger=ledger).run(AGENT_PREFS)
    row = result.listings[0]
    assert row.found_via == "agent" and row.source_url == PORTAL.url and row.apply_url == URL
    assert row.verification == "uncertain" and row.call_status == "unknown" and not row.requirements
    assert result.usage["agent_runs"] == 0 and row.locations == ["Berlin"]


def test_verified_default_agent_cap_reserves_default_step_rate_once_under_total_budget(tmp_path):
    ledger = MemoryLedger(); browser = AgentBrowser()
    config = {**AGENT_CONFIG, "tinyfish_agent_step_cap_verified": False, "tinyfish_agent_default_cap_verified": True,
              "tinyfish_agent_max_steps": 150, "tinyfish_agent_step_cost_usd": 0.016}
    result = engine(tmp_path, Web([], [PORTAL]), ledger=ledger, browser=browser, **config).run(AGENT_PREFS)
    assert browser.finds == 1 and result.usage["agent_runs"] == 1
    assert sum(amount for name, amount in ledger.reservations if name == "agent_session_usd") == pytest.approx(2.40)


@pytest.mark.parametrize("steps,rate", [(149, 0.016), (151, 0.016), (True, 0.016), (150, 0), (150, -0.016), (150, float("nan")), (150, float("inf"))])
def test_default_cap_mismatch_or_invalid_rate_rejected_before_lease_or_charge(tmp_path, steps, rate):
    ledger = MemoryLedger(); browser = AgentBrowser()
    config = {**AGENT_CONFIG, "tinyfish_agent_step_cap_verified": False, "tinyfish_agent_default_cap_verified": True,
              "tinyfish_agent_max_steps": steps, "tinyfish_agent_step_cost_usd": rate}
    result = engine(tmp_path, Web([], [PORTAL]), ledger=ledger, browser=browser, **config).run(AGENT_PREFS)
    assert browser.finds == 0 and result.usage["agent_runs"] == 0 and not ledger.values
    assert not any(name == "agent_session_usd" for name, amount in ledger.reservations)
    assert any("step/spend cap" in error for error in result.errors)


@pytest.mark.parametrize("slug", ["rapyuta-robotics", "lattice-research"])
def test_workable_feed_uses_markdown_and_actual_unscoped_url_not_manufactured_org_path(tmp_path, slug):
    import json
    from app.discovery.urls import detect_ats
    board = f"https://apply.workable.com/{slug}"
    feed = detect_ats(board).feed_url
    target = "https://apply.workable.com/j/3EE3968348"
    feed_page = page(feed, json.dumps({"name": "Rapyuta Robotics", "jobs": [
        {"title": "Software Engineer Intern", "shortcode": "3EE3968348", "url": target}]}))
    class MarkdownWeb(Web):
        def fetch(self, urls, format="markdown", ttl=0):
            assert format == "markdown"
            return super().fetch(urls, format=format, ttl=ttl)
    web = MarkdownWeb([feed_page, page(target)], [SourceLead(url=board)])
    result = engine(tmp_path, web).run(PREFS)
    assert web.reads == [feed, target] and result.listings[0].apply_url == target


def test_workday_filtered_board_then_selected_posting_without_board_ai_call(tmp_path):
    board = "https://lattice.wd5.myworkdayjobs.com/External"
    requested = board + "?q=intern"
    target = board + "/job/Berlin/Software-Engineer-Intern_R12000"
    board_page = page(board)
    board_page.requested_url = requested
    board_page.links = [target, board + "/job/Berlin/Senior-Software-Engineer_R10000"]
    web = Web([board_page, page(target)], [SourceLead(url=board)])
    extractor = Extractor()
    result = engine(tmp_path, web, extractor).run(PREFS)
    assert web.reads == [requested, target] and extractor.calls == [target]
    assert result.listings


def test_linked_ats_posting_discovers_parent_feed_and_follows_new_board_openings(tmp_path):
    from app.discovery.urls import detect_ats
    careers = "https://careers.lattice.org/careers"
    board = "https://job-boards.greenhouse.io/lattice-research"
    first = board + "/jobs/12001"
    second = board + "/jobs/12002"
    feed = detect_ats(board).feed_url
    careers_page = page(careers, f"# Careers\n[Software Engineer Intern]({first})")
    feed_page = page(feed); feed_page.json_body = {"jobs": [
        {"id": 12001, "title": "Software Engineer Intern"}, {"id": 12002, "title": "Software Engineer Intern"}]}
    outputs = Outputs({careers: ExtractionResult(page_type="index"),
                       first: ExtractionResult(page_type="posting", listings=[listing(first)]),
                       second: ExtractionResult(page_type="posting", listings=[listing(second)])})
    web = Web([careers_page, feed_page, page(first), page(second)], [SourceLead(url=careers)])
    result = engine(tmp_path, web, outputs).run(PREFS)
    assert web.reads == [careers, feed, first, second] and len(result.listings) == 2


def test_tagged_local_rate_warning_not_treated_as_fatal_unavailable(tmp_path):
    other = "https://careers.lattice.org/jobs/80009"
    warning = "Groq shared token budget still unavailable after one reset wait; no further request was made. [AI:rate_limit]"
    outputs = Outputs({URL: ExtractionResult(warnings=[warning]),
                       other: ExtractionResult(page_type="posting", listings=[listing(other)])})
    result = engine(tmp_path, Web([page(), page(other)], [SourceLead(url=URL), SourceLead(url=other)]), outputs).run(PREFS)
    assert len(outputs.calls) == 2 and result.listings and result.partial


def test_paced_retry_reserves_each_actual_ai_attempt_against_daily_budget(tmp_path):
    class Paced(Extractor):
        def extract(self, p, prefs, lead, remaining_seconds=None, on_call=None):
            from app.discovery.ai import AIError
            on_call()
            self.calls.append("first")
            try:
                on_call()
            except AIError as exc:
                return ExtractionResult(warnings=[str(exc)])
            self.calls.append("retry")
            return super().extract(p, prefs, lead)
    ledger = MemoryLedger(); extractor = Paced()
    result = engine(tmp_path, Web([page()]), extractor, ledger=ledger, discovery_daily_ai_calls=1).run(PREFS)
    assert extractor.calls == ["first"] and result.usage["ai_attempts"] == 1
    assert sum(amount for name, amount in ledger.reservations if name == "ai_calls") == 1
    assert result.partial and any("paced retry" in error for error in result.errors)


def test_relevance_precedes_per_query_page_ceiling_not_only_fetch_budget(tmp_path, monkeypatch):
    monkeypatch.setattr("app.discovery.engine.plan_searches", lambda prefs: [SearchTask(intent="web", query="jobs", purpose="", label="jobs")])
    target = "https://careers.lattice.org/jobs/90001"
    leads = [SourceLead(url=f"https://careers.orbital.org/jobs/{i+10000}", title="Senior Software Engineer") for i in range(15)]
    leads.extend(SourceLead(url=f"https://careers.orbital.org/jobs/{i+20000}", title="Marketing Intern") for i in range(15))
    leads.append(SourceLead(url=target, title="Software Engineer Intern"))
    web = Web([page(target)], leads)
    result = engine(tmp_path, web).run(PREFS, budget=RunBudget(max_fetch_urls=1))
    assert web.reads == [target] and result.listings


def test_default_cap_conservative_total_reservation_blocks_second_distinct_goal(tmp_path):
    class GoalBrowser(AgentBrowser):
        def cache_key(self, lead, prefs):
            return lead.url
    ledger = MemoryLedger(); browser = GoalBrowser()
    portals = [SourceLead(url="https://jobs.ashbyhq.com/OrbitalDynamics"), SourceLead(url="https://jobs.ashbyhq.com/LatticeResearch")]
    config = {**AGENT_CONFIG, "tinyfish_agent_step_cap_verified": False, "tinyfish_agent_default_cap_verified": True,
              "tinyfish_agent_max_steps": 150, "tinyfish_agent_step_cost_usd": 0.016}
    result = engine(tmp_path, Web([], portals), ledger=ledger, browser=browser, **config).run(
        PREFS.model_copy(update={"companies": ["Orbital Dynamics", "Lattice Research"]}))
    assert browser.finds == result.usage["agent_runs"] == 1
    assert sum(amount for name, amount in ledger.reservations if name == "agent_session_usd") == pytest.approx(2.40)
    assert any("budget exhausted" in error for error in result.errors)


def test_feed_evidence_bridge_scopes_two_distinct_titles_without_cross_job_facts(tmp_path):
    from app.discovery.bridge import listing_to_opportunities
    from app.discovery.urls import detect_ats
    board = "https://jobs.lever.co/orbital-dynamics"
    feed = detect_ats(board).feed_url
    rows = [{"text": title, "hostedUrl": board + "/" + uuid,
             "descriptionPlain": "Build scientific software for real experiments. " * 8,
             "lists": [{"text": "Basic Qualifications", "content": f"<li>{skill} required.</li>"}]}
            for title, uuid, skill in [
                ("Software Engineer Intern", "12345678-1234-1234-1234-123456789abc", "Python"),
                ("ML Engineer Intern", "12345678-1234-1234-1234-123456789abd", "Java")]]
    feed_page = page(feed, "Raw public feed retained"); feed_page.json_body = rows
    class ScopedExtractor:
        def extract(self, p, prefs, lead, remaining_seconds=None):
            skill = "Python" if lead.title.startswith("Software") else "Java"
            assert lead.evidence_transform == "decoded_json_html_feed_row_with_title_scope"
            return ExtractionResult(page_type="posting", listings=[listing(lead.url, title=lead.title, source_url=p.snapshot.url,
                requirements=[Fact(name="skills", value=[skill], kind="requirement", status="known", excerpt=f"{skill} required.",
                                   source_url=p.snapshot.url, source_id=p.snapshot.id)])])
    result = engine(tmp_path, Web([feed_page], [SourceLead(url=board)]), ScopedExtractor()).run(
        PREFS.model_copy(update={"roles": ["software engineer", "ML engineer"]}))
    evidence = result.pages[-1]
    assert evidence.snapshot.url == evidence.requested_url == feed
    assert evidence.snapshot.checked_at == feed_page.snapshot.checked_at
    assert "decoded public ATS feed row" in evidence.snapshot.text
    assert len(result.listings) == 2
    for row in result.listings:
        opportunity = listing_to_opportunities(row, evidence)[0]
        skill = next(f for f in opportunity.facts if f.name == "skills")
        assert skill.status == "known" and skill.value == row.requirements[0].value


def test_feed_row_safety_truncation_is_visible_not_reported_complete(tmp_path):
    board = "https://job-boards.greenhouse.io/lattice-research"
    feed = "https://boards-api.greenhouse.io/v1/boards/lattice-research/jobs"
    feed_page = page(feed)
    feed_page.json_body = {"jobs": [{"id": i+1000, "title": "Marketing Intern"} for i in range(1001)]}
    result = engine(tmp_path, Web([feed_page], [SourceLead(url=board)])).run(PREFS)
    assert result.partial and any("row safety limit" in error for error in result.errors)


def test_nonempty_feed_with_only_invalid_rows_is_failed_not_empty_board(tmp_path):
    board = "https://apply.workable.com/lattice-research"
    feed = "https://apply.workable.com/api/v1/widget/accounts/lattice-research"
    feed_page = page(feed); feed_page.json_body = {"jobs": [{"title": "Software Intern", "url": "http://localhost/jobs/1000"}]}
    result = engine(tmp_path, Web([feed_page], [SourceLead(url=board)])).run(PREFS)
    assert result.partial and any("could not be parsed" in error for error in result.errors)
    assert not any(e.stage == "source" and e.url == feed and ": empty" in e.message for e in result.events)


def test_scout_top_sixty_current_matches_with_prior_history_preserved(tmp_path):
    urls = [f"https://careers.lattice.org/jobs/{i+90000}" for i in range(65)]
    outputs = Outputs({URL: ExtractionResult(page_type="posting", listings=[listing(url) for url in urls])})
    def ordered(prefs, rows, settings=None, remaining_seconds=None):
        return [row.model_copy(update={"score": 100-(int(row.apply_url.rsplit("/", 1)[1])-90000)}) for row in rows]
    prior = listing(urls[-1], saved=True, id="saved-lower-score")
    result = engine(tmp_path, Web([page()]), outputs, ranking=ordered).run(PREFS, previous=[prior])
    assert len(result.listings) == 61
    assert len([row for row in result.listings if row.score > 0]) == 60
    assert result.listings[-1].id == prior.id and result.listings[-1].saved
