"""Refresh regressions use a disposable real FalkorDB graph and ASGI routes.

TinyFish is served by MockTransport from recorded public source text. These are
API/graph integration proofs, not live provider proofs. Database absence fails
this suite explicitly; no mock database or silent skip can satisfy the cases.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.config import Settings, settings
from app.graph import GraphStore
from app.models import ProfileState, SourceSnapshot
from app.planner import build_plan
from app.sources import DiscoverService, OIST_APPLY, OIST_SUPPORT, TinyFishClient


DATA = Path(__file__).resolve().parents[1] / "data" / "source_snapshots"
SPRING = "oist-spring-2027"
FALL = "oist-fall-2027"


@pytest.fixture
def api(monkeypatch):
    name = "just_chill_api_refresh_test_" + uuid4().hex
    config = replace(settings, db_host="127.0.0.1", db_port=16379, db_graph=name)
    graph = GraphStore(config)
    assert graph.health()["status"] == "ok", "Real local FalkorDB is unavailable; API refresh proof cannot pass."
    monkeypatch.setattr(main, "store", graph)
    monkeypatch.setattr(main, "settings", replace(settings, demo_tools_enabled=True))
    try:
        with TestClient(main.app) as client:
            yield client, graph, monkeypatch
    finally:
        # The task explicitly authorizes a disposable test graph. Never delete
        # the configured application graph or any graph we did not create.
        assert name.startswith("just_chill_api_refresh_test_") and name != settings.db_graph
        db = graph._db()
        if name in db.list_graphs():
            db.select_graph(name).delete()
        db.close()


def recorded(name: str, *, text: str | None = None) -> SourceSnapshot:
    original = SourceSnapshot.model_validate_json((DATA / name).read_text())
    # Mode reflects the test provider response, not a new real web fetch.
    content = original.text if text is None else text
    return original.model_copy(update={"text": content, "mode": "live",
                                       "content_hash": hashlib.sha256(content.encode()).hexdigest()})


def facts(opportunity):
    return {fact.name: fact for fact in opportunity.facts}


def provider(api, pages: list[SourceSnapshot], *, failed: dict[str, str] | None = None):
    client, graph, monkeypatch = api
    by_url = {page.url: page for page in pages}
    failures = failed or {}

    def request_handler(request):
        assert request.method == "POST"
        assert request.url.host == "api.fetch.tinyfish.ai"
        requested = json.loads(request.content)["urls"]
        return httpx.Response(200, json={
            "results": [{"url": url, "title": by_url[url].title, "text": by_url[url].text}
                        for url in requested if url in by_url and url not in failures],
            "errors": [{"url": url, "error": failures[url]} for url in requested if url in failures],
        })

    tinyfish = TinyFishClient(Settings(tinyfish_key="fixture-only-placeholder"),
                              transport=httpx.MockTransport(request_handler))
    monkeypatch.setattr(main, "sources", DiscoverService(client=tinyfish))
    return client, graph


def refresh(api, pages: list[SourceSnapshot], *, failed: dict[str, str] | None = None,
            url: str = OIST_APPLY):
    client, _ = provider(api, pages, failed=failed)
    response = client.post("/api/refresh", json={"url": url})
    assert response.status_code == 200, response.text
    return response.json()


def seed(api):
    refresh(api, [recorded("oist.json"), recorded("oist_support.json")])
    _, graph, _ = api
    assert graph.get_opportunity(SPRING)
    assert graph.get_opportunity(FALL)
    return graph


def save_proposal(graph: GraphStore, ids: list[str]):
    profile = ProfileState(id="refresh-profile-" + uuid4().hex)
    proposal = build_plan(graph.context(ids), profile)
    return graph.save_plan(proposal)


def latest(client: TestClient, profile: ProfileState):
    response = client.get("/api/plan/latest", params={"profile_id": profile.id})
    assert response.status_code == 200, response.text
    return response.json()["plan"]


def test_all_oist_cohorts_disappear_retains_unknown_and_stales_prior_plan(api):
    graph = seed(api)
    old = graph.get_opportunity(FALL)
    old_deadline = facts(old)["application_deadline"]
    proposal = save_proposal(graph, [SPRING, FALL])
    client, _, _ = api
    missing = recorded("oist.json", text="# Apply to Research Internship\nSchedule temporarily unavailable.")
    payload = refresh(api, [missing, recorded("oist_support.json")])

    assert payload["source_outcomes"][0]["status"] == "partial"
    for target_id in (SPRING, FALL):
        retained = graph.get_opportunity(target_id)
        assert retained.verification == "uncertain"
        assert retained.call_status == "unknown"
        assert all(fact.status == "unknown" for fact in retained.facts if fact.source_url == OIST_APPLY)
    retained_deadline = facts(graph.get_opportunity(FALL))["application_deadline"]
    assert retained_deadline.value == old_deadline.value
    assert retained_deadline.excerpt == old_deadline.excerpt
    assert retained_deadline.version_id != old_deadline.version_id
    stored = latest(client, proposal.profile)
    assert stored["status"] == "stale"
    assert set(stored["affected_target_ids"]) == {SPRING, FALL}
    assert client.post(f"/api/plan/{proposal.id}/accept").status_code == 409


def test_one_cohort_disappears_only_missing_target_unknown_and_stale(api):
    graph = seed(api)
    spring = graph.get_opportunity(SPRING)
    spring_versions = {fact.name: fact.version_id for fact in spring.facts}
    spring_plan = save_proposal(graph, [SPRING])
    fall_plan = save_proposal(graph, [FALL])
    client, _, _ = api
    only_spring = "\n".join(line for line in recorded("oist.json").text.splitlines()
                             if "Fall 2027 Internship" not in line)
    payload = refresh(api, [recorded("oist.json", text=only_spring), recorded("oist_support.json")])

    apply_outcome = next(item for item in payload["source_outcomes"] if item["url"] == OIST_APPLY)
    assert apply_outcome["opportunity_ids"] == [SPRING]
    assert {fact.name: fact.version_id for fact in graph.get_opportunity(SPRING).facts} == spring_versions
    assert facts(graph.get_opportunity(FALL))["application_deadline"].status == "unknown"
    assert latest(client, spring_plan.profile)["status"] == "proposed"
    assert latest(client, fall_plan.profile)["status"] == "stale"
    assert client.post(f"/api/plan/{spring_plan.id}/accept").status_code == 200
    assert client.post(f"/api/plan/{fall_plan.id}/accept").status_code == 409


def test_remaining_cohort_updates_while_failed_support_stays_unknown(api):
    graph = seed(api)
    old_funding = facts(graph.get_opportunity(FALL))["funding"]
    proposal = save_proposal(graph, [FALL])
    client, _, _ = api
    changed = recorded("oist.json").text.replace("no more than 250 words (1500 characters)",
                                                  "no more than 200 words (1200 characters)")
    changed = "\n".join(line for line in changed.splitlines() if "Spring 2027 Internship" not in line)
    payload = refresh(api, [recorded("oist.json", text=changed)], failed={OIST_SUPPORT: "timeout"})

    outcome = {item["url"]: item for item in payload["source_outcomes"]}
    assert outcome[OIST_APPLY]["opportunity_ids"] == [FALL]
    assert outcome[OIST_SUPPORT]["status"] == "failed"
    current = graph.get_opportunity(FALL)
    assert facts(current)["statement_max_words"].status == "known"
    assert facts(current)["statement_max_words"].value == 200
    assert facts(current)["statement_max_chars"].value == 1200
    assert facts(current)["application_deadline"].status == "known"
    assert facts(current)["funding"].status == "unknown"
    assert facts(current)["funding"].source_url == OIST_SUPPORT
    assert facts(current)["funding"].source_id == old_funding.source_id
    assert facts(current)["funding"].excerpt == old_funding.excerpt
    assert facts(graph.get_opportunity(SPRING))["documents"].status == "unknown"
    assert latest(client, proposal.profile)["status"] == "stale"
    assert client.post(f"/api/plan/{proposal.id}/accept").status_code == 409


def test_source_recovery_restores_known_evidence_without_reviving_old_proposal(api):
    graph = seed(api)
    proposal = save_proposal(graph, [FALL])
    client, _, _ = api
    refresh(api, [], failed={OIST_APPLY: "bot_blocked", OIST_SUPPORT: "timeout"})
    assert facts(graph.get_opportunity(FALL))["documents"].status == "unknown"
    assert latest(client, proposal.profile)["status"] == "stale"
    payload = refresh(api, [recorded("oist.json"), recorded("oist_support.json")])

    assert all(item["status"] == "success" for item in payload["source_outcomes"])
    current = graph.get_opportunity(FALL)
    assert facts(current)["documents"].status == "known"
    assert facts(current)["application_deadline"].status == "known"
    assert facts(current)["funding"].status == "known"
    # Old proposals were invalidated by a real gap. Source recovery is not
    # user approval and does not clear their recorded staleness.
    assert latest(client, proposal.profile)["status"] == "stale"
    assert client.post(f"/api/plan/{proposal.id}/accept").status_code == 409
    fresh = save_proposal(graph, [FALL])
    assert client.post(f"/api/plan/{fresh.id}/accept").status_code == 200


def test_cached_examples_do_not_overwrite_newer_live_facts(api):
    graph = seed(api)
    changed = recorded("oist.json").text.replace("no more than 250 words (1500 characters)",
                                                  "no more than 200 words (1200 characters)")
    refresh(api, [recorded("oist.json", text=changed), recorded("oist_support.json")])
    proposal = save_proposal(graph, [FALL])
    before = facts(graph.get_opportunity(FALL))["statement_max_words"]
    client, _, _ = api
    response = client.post("/api/examples")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["mode"] == "cached"
    assert any(item.get("skipped_cached_rollback") == FALL for item in payload["impacts"])
    after = facts(graph.get_opportunity(FALL))["statement_max_words"]
    assert after.value == 200
    assert after.version_id == before.version_id
    assert graph.get_opportunity(FALL).mode == "live"
    assert latest(client, proposal.profile)["status"] == "proposed"
    assert client.post(f"/api/plan/{proposal.id}/accept").status_code == 200
