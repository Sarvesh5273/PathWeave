from concurrent.futures import ThreadPoolExecutor

import pytest

from app.discovery.contracts import DiscoveryListing, DiscoveryPreferences, EngineResult, RunEvent
from app.discovery.state import DiscoveryState, StateError


def state(tmp_path):
    return DiscoveryState(str(tmp_path/"state.sqlite"))


def test_hunts_browser_scoped_and_persist_across_instances(tmp_path):
    ledger=state(tmp_path)
    hunt=ledger.create_hunt("browser-one",DiscoveryPreferences(roles=["software engineer"]))
    assert state(tmp_path).hunt(hunt["id"],"browser-one")["preferences"]["roles"]==["software engineer"]
    with pytest.raises(StateError):
        ledger.hunt(hunt["id"],"browser-two")
    assert ledger.hunts("browser-two")==[]


def test_one_active_run_per_hunt_and_status_events(tmp_path):
    ledger=state(tmp_path);hunt=ledger.create_hunt("browser",DiscoveryPreferences(roles=["software engineer"]))
    first=ledger.enqueue(hunt["id"],"browser");second=ledger.enqueue(hunt["id"],"browser")
    assert first["id"]==second["id"]
    assert ledger.claim(first["id"]) and not ledger.claim(first["id"])
    ledger.event(first["id"],RunEvent(stage="search",message="Actual stage"))
    ledger.finish(first["id"],EngineResult())
    run=ledger.run(first["id"],"browser")
    assert run["status"]=="completed" and run["events"][0]["stage"]=="search"


def test_atomic_budget_reservations_never_overspend(tmp_path):
    ledger=state(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as executor:
        values=list(executor.map(lambda _:ledger.reserve("agent",0.4,3,window=10**15),range(20)))
    assert sum(values)==7
    assert not state(tmp_path).reserve("agent",0.4,3,window=10**15)


def test_cache_expiry_and_restart_interruption(tmp_path):
    ledger=state(tmp_path)
    ledger.cache("key",{"ok":True},100)
    assert state(tmp_path).cached("key")=={"ok":True}
    ledger.cache("key",{},-1)
    assert ledger.cached("key") is None
    hunt=ledger.create_hunt("browser",DiscoveryPreferences(roles=["software engineer"]))
    run=ledger.enqueue(hunt["id"],"browser");ledger.claim(run["id"])
    ledger.recover_interrupted()
    assert ledger.run(run["id"],"browser")["status"]=="interrupted"


def test_atomic_inflight_goal_acquisition_and_queued_worker_access(tmp_path):
    ledger=state(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as executor:
        values=list(executor.map(lambda _:ledger.acquire("portal",{"run_id":None},100),range(10)))
    assert sum(values)==1
    ledger.delete_cache("portal")
    assert ledger.acquire("portal",{},100)
    hunt=ledger.create_hunt("browser",DiscoveryPreferences(roles=["software engineer"]))
    run=ledger.enqueue(hunt["id"],"browser")
    assert run["id"] in ledger.queued()
    assert ledger.job_hunt(run["id"])["preferences"]["roles"]==["software engineer"]


def test_new_listing_flags_and_source_results_are_separate(tmp_path):
    ledger=state(tmp_path);hunt=ledger.create_hunt("browser",DiscoveryPreferences(roles=["software engineer"]))
    listing=DiscoveryListing(id="listing-1",title="Intern",apply_url="https://employer.example/jobs/1",source_url="https://employer.example/jobs/1",checked_at="2026-10-16T10:00:00Z")
    run=ledger.enqueue(hunt["id"],"browser");ledger.claim(run["id"])
    ledger.finish(run["id"],EngineResult(listings=[listing]))
    assert ledger.hunt(hunt["id"],"browser")["result"]["listings"][0]["is_new"]
    ledger.flags(hunt["id"],"listing-1","browser",saved=True,hidden=True)
    run=ledger.enqueue(hunt["id"],"browser");ledger.claim(run["id"])
    ledger.finish(run["id"],EngineResult(listings=[listing]))
    returned=ledger.hunt(hunt["id"],"browser")["result"]["listings"][0]
    assert returned["saved"] and returned["hidden"] and not returned["is_new"]


def test_run_status_reports_actual_zero_results_without_dumping_snapshots(tmp_path):
    ledger=state(tmp_path)
    hunt=ledger.create_hunt("browser",DiscoveryPreferences(roles=["software engineer"]))
    run=ledger.enqueue(hunt["id"],"browser")
    ledger.claim(run["id"])
    ledger.finish(run["id"],EngineResult(partial=True,errors=["Source extraction failed"]))
    record=ledger.run(run["id"],"browser")
    assert record["status"]=="partial" and record["listing_count"]==0
    assert "hunt_result" not in record


def test_live_progress_is_visible_without_erasing_old_result_or_new_flags(tmp_path):
    ledger=state(tmp_path)
    hunt=ledger.create_hunt("browser",DiscoveryPreferences(roles=["software engineer"]))
    run=ledger.enqueue(hunt["id"],"browser");ledger.claim(run["id"])
    listing=DiscoveryListing(id="listing-1",title="Software Intern",apply_url="https://company.example/jobs/1",source_url="https://company.example/jobs/1",checked_at="2026-10-16T00:00:00Z")
    result=EngineResult(listings=[listing])
    ledger.progress(run["id"],result)
    assert ledger.run(run["id"],"browser")["listing_count"]==1
    assert ledger.hunt(hunt["id"],"browser")["result"]["listings"][0]["id"]==listing.id
    assert ledger.job_hunt(run["id"])["result"] is None
    ledger.finish(run["id"],result)
    assert ledger.hunt(hunt["id"],"browser")["result"]["listings"][0]["is_new"]


def test_opt_in_scheduler_due_active_hunts_no_duplicate_jobs(tmp_path):
    ledger=state(tmp_path)
    active=ledger.create_hunt("browser",DiscoveryPreferences(roles=["software engineer"]))
    inactive=ledger.create_hunt("browser",DiscoveryPreferences(roles=["robotics intern"]))
    with ledger._db() as db:
        db.execute("UPDATE hunts SET next_refresh=0")
        db.execute("UPDATE hunts SET viewed=0 WHERE id=?",(inactive["id"],))
    scheduled=ledger.schedule_due()
    assert len(scheduled)==1
    assert ledger.job_hunt(scheduled[0])["id"]==active["id"]
    assert ledger.schedule_due()==[]
