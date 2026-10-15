from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.models import SourceSnapshot
from app.sources import (
    FETCH_ENDPOINT,
    OIST_APPLY,
    SEARCH_ENDPOINT,
    SHARED_FIELDS,
    DiscoverService,
    TinyFishClient,
    TinyFishError,
    parse_snapshot,
)


DATA = Path(__file__).resolve().parents[1] / "data" / "source_snapshots"


def snapshot(name: str) -> SourceSnapshot:
    return SourceSnapshot.model_validate_json((DATA / name).read_text())


def fact_map(opportunity):
    return {fact.name: fact for fact in opportunity.facts}


def minimal(text: str, url: str = "https://unknown.example.org/internship") -> SourceSnapshot:
    return SourceSnapshot(id="test-source", url=url, title="Internship", text=text)


def test_recorded_epfl_closed_next_cohort_and_reference_exception():
    original = snapshot("epfl.json")
    opportunity, = parse_snapshot(original)
    facts = fact_map(opportunity)
    assert opportunity.id == "epfl-summer-2027"
    assert opportunity.cycle == "Summer 2027"
    assert opportunity.call_status == "closed"
    deadline = datetime.fromisoformat(facts["application_deadline"].value)
    assert deadline.utcoffset() == timedelta(hours=-12)
    assert deadline.astimezone(timezone.utc).isoformat() == "2026-11-30T11:39:00+00:00"
    assert facts["reference_min"].value == 0
    assert facts["reference_forbidden"].value is True
    assert "reference" not in facts["documents"].value
    assert facts["transcript_translation"].value == "self"
    assert facts["fee_amount"].status == "unknown"  # Funding/absence cannot imply zero fee.
    assert facts["statement_max_pages"].value == 2


def test_recorded_oist_fall_is_not_open_from_future_date_or_apply_now():
    opportunities = parse_snapshot(snapshot("oist.json"))
    by_id = {op.id: op for op in opportunities}
    fall = by_id["oist-fall-2027"]
    spring = by_id["oist-spring-2027"]
    facts = fact_map(fall)
    assert facts["application_deadline"].value == "2027-04-15T23:59:00+09:00"
    assert fall.call_status == "unknown"
    assert facts["portal_status"].status == "unknown"
    assert spring.call_status == "closed"
    assert facts["reference_min"].value == 1
    assert facts["reference_received_before_submit"].value is True
    assert facts["reference_submitter"].value == "professorial_level_faculty"
    assert facts["applicant_reference_upload_allowed"].value is False
    assert facts["statement_max_words"].value == 250
    assert facts["statement_max_chars"].value == 1500
    assert facts["fee_amount"].value == 5000
    assert facts["fee_currency"].value == "JPY"
    assert facts["transcript_translation"].value == "english_explanation"
    assert facts["institution_approval"].value is True
    assert facts["max_years_remaining"].value == 2
    assert facts["min_study_year"].status == "unknown"
    assert "diploma_or_enrollment" in facts["documents"].value
    assert "english_score" not in facts["documents"].value


def test_oist_cycle_specific_status_does_not_cross_apply():
    original = snapshot("oist.json")
    original.text += "\nApplications for Fall 2027 are now open.\n"
    by_id = {op.id: op for op in parse_snapshot(original)}
    assert by_id["oist-fall-2027"].call_status == "open"
    assert fact_map(by_id["oist-spring-2027"])["portal_status"].status == "unknown"


def test_every_supported_known_fact_has_exact_source_evidence():
    examples = DiscoverService().load_examples()
    by_source = {item.id: item for item in examples.snapshots}
    assert not examples.errors
    assert len(examples.snapshots) == 5
    for opportunity in examples.opportunities:
        assert set(SHARED_FIELDS) <= set(fact_map(opportunity))
        for fact in opportunity.facts:
            if fact.status == "known":
                assert fact.excerpt
                source = by_source[fact.source_id]
                assert fact.excerpt in source.text
                assert fact.source_url == source.url
                assert not fact.simulated
                assert datetime.fromisoformat(source.checked_at.replace("Z", "+00:00")).tzinfo


def test_google_right_to_work_is_preference_and_window_not_exact_deadline():
    opportunity, = parse_snapshot(snapshot("google_fde.json"))
    facts = fact_map(opportunity)
    assert opportunity.id == "google-fde-2027"
    assert opportunity.category == "Company"
    assert opportunity.call_status == "unknown"
    assert facts["work_authorization_preference"].kind == "preference"
    assert facts["application_deadline"].status == "unknown"
    assert facts["application_window_end"].value == "2026-11-15"
    assert facts["application_window_end"].kind == "information"
    assert facts["rolling_early_close"].value is True
    assert facts["year_constraint"].value["type"] == "penultimate"
    assert facts["documents"].status == "unknown"
    assert facts["fee_amount"].status == "unknown"  # Agency fee boilerplate isn't an applicant fee.
    assert facts["software_development_experience"].kind == "requirement"
    assert facts["preferred_qualifications"].kind == "preference"


def test_mitacs_closed_and_india_scope_not_other_partner_rules():
    opportunity, = parse_snapshot(snapshot("mitacs.json"))
    facts = fact_map(opportunity)
    assert opportunity.id == "mitacs-summer-2027"
    assert opportunity.call_status == "closed"
    assert facts["eligibility_scope"].value == "India"
    assert facts["citizenship_requirement"].value == "India"
    assert facts["excluded_institution_types"].value == ["iit"]
    assert facts["minimum_grade_percent"].value == 70
    assert facts["degree_program_types"].value == ["be", "btech"]
    assert facts["degree_program_types"].kind == "requirement"
    assert "Engineering (B.E)" in facts["degree_program_types"].excerpt
    assert facts["fields"].status == "unknown"
    assert facts["fields"].kind == "information"
    assert facts["transcript_translation"].value == "notarized"
    assert facts["institution_listed"].value is True
    assert facts["application_deadline"].status == "unknown"


def test_generic_source_does_not_invent_rules_from_snippets():
    opportunity, = parse_snapshot(minimal("Applications open soon. The next deadline is November 15. Fully funded!"))
    assert opportunity.cycle == "unknown"
    assert opportunity.call_status == "unknown"
    assert opportunity.verification == "partial"
    assert all(f.status == "unknown" and f.value is None for f in opportunity.facts)


def test_no_historical_cycle_rollover_or_inferred_next_deadline():
    text = "# Summer@EPFL\nApplications are now CLOSED!\nThe next deadline is\n29th November 2023 (23:39 AOE)\nfor internships in summer 2024."
    opportunity, = parse_snapshot(minimal(text, "https://summer.epfl.ch/apply.html"))
    assert opportunity.id == "epfl-summer-2024"
    assert fact_map(opportunity)["application_deadline"].value == "2023-11-29T23:39:00-12:00"
    assert opportunity.call_status == "closed"


def test_missing_cohort_and_deadline_zone_do_not_acquire_known_values():
    opportunity, = parse_snapshot(minimal("# Summer@EPFL\nApplications are now CLOSED!", "https://summer.epfl.ch/apply.html"))
    assert opportunity.cycle == "unknown"
    assert fact_map(opportunity)["application_deadline"].status == "unknown"
    original = snapshot("epfl.json")
    original.text = original.text.replace("23:39 AOE", "23:39")
    opportunity, = parse_snapshot(original)
    assert opportunity.id == "epfl-summer-2027"
    assert fact_map(opportunity)["application_deadline"].status == "unknown"
    assert fact_map(opportunity)["application_deadline"].excerpt in original.text


def test_conflicting_status_and_statement_limits_not_certified():
    original = snapshot("epfl.json")
    original.text += "\nApplications are now OPEN!\n"
    opportunity, = parse_snapshot(original)
    assert fact_map(opportunity)["portal_status"].status == "conflicting"
    assert opportunity.verification == "uncertain"
    original = snapshot("oist.json")
    original.text += "\nStatement: no more than 300 words (1800 characters)\n"
    for opportunity in parse_snapshot(original):
        facts = fact_map(opportunity)
        assert facts["statement_max_words"].status == "conflicting"
        assert facts["statement_max_chars"].status == "conflicting"
        assert facts["statement_max_words"].excerpt in original.text


def test_boilerplate_changes_do_not_change_semantic_source_facts():
    original = snapshot("epfl.json")
    before = parse_snapshot(original)[0]
    original.text += "\nFooter updated. Copyright 2026.\n"
    after = parse_snapshot(original)[0]
    values = lambda op: [(f.name, f.value, f.status, f.kind) for f in op.facts]
    assert values(before) == values(after)


def test_changed_receipt_evidence_becomes_unknown_without_false_absence():
    original = snapshot("oist.json")
    original.text = original.text.replace("You may submit your application only after at least one recommendation letter is received", "Recommendation receipt policy is temporarily unavailable")
    for opportunity in parse_snapshot(original):
        receipt = fact_map(opportunity)["reference_received_before_submit"]
        assert receipt.status == "unknown"
        assert receipt.value is None
        assert fact_map(opportunity)["reference_min"].value == 1


def test_partial_oist_document_section_does_not_become_known_empty_or_complete():
    text = "# Application Documents\nThe document list is temporarily unavailable.\n# Application Fee\n"
    opportunity, = parse_snapshot(minimal(text, OIST_APPLY))
    assert fact_map(opportunity)["documents"].status == "unknown"
    assert fact_map(opportunity)["documents"].value is None


def test_missing_oist_identity_document_is_not_inferred_no_requirement():
    original = snapshot("oist.json")
    start = original.text.index("5. **Passport**")
    end = original.text.index("6. **ID Photo**", start)
    original.text = original.text[:start] + original.text[end:]
    for opportunity in parse_snapshot(original):
        assert fact_map(opportunity)["documents"].status == "unknown"


def test_oist_conflicting_cycle_portal_status_stays_uncertain():
    original = snapshot("oist.json")
    original.text += "\nApplications for Fall 2027 are open.\nApplications for Fall 2027 are closed.\n"
    fall = next(op for op in parse_snapshot(original) if op.id == "oist-fall-2027")
    assert fact_map(fall)["portal_status"].status == "conflicting"
    assert fall.call_status == "unknown"
    assert fall.verification == "uncertain"


def test_oist_round_identity_survives_missing_deadline_evidence():
    original = snapshot("oist.json")
    original.text = original.text.replace("April 15th, 2027, 23:59 (JST UTC+9)", "To be announced")
    by_id = {op.id: op for op in parse_snapshot(original)}
    assert "oist-fall-2027" in by_id
    assert fact_map(by_id["oist-fall-2027"])["application_deadline"].status == "unknown"
    assert by_id["oist-fall-2027"].call_status == "unknown"


def test_removed_oist_degree_does_not_survive_as_known_field():
    original = snapshot("oist.json")
    original.text = original.text.replace("master's degree", "unpublished qualification")
    for opportunity in parse_snapshot(original):
        assert "master" not in fact_map(opportunity)["degree_levels"].value


def client_with(handler):
    return TinyFishClient(Settings(tinyfish_key="test-secret-do-not-print"), transport=httpx.MockTransport(handler))


def test_http_request_contract_and_live_content_integrity():
    calls = []
    def handler(request):
        calls.append(request)
        assert request.headers["X-API-Key"] == "test-secret-do-not-print"
        assert all(v > 0 and v <= 40 for v in request.extensions["timeout"].values())
        if request.url.host == "api.search.tinyfish.ai":
            assert request.method == "GET"
            assert request.url.params["query"] == "research internship"
            return httpx.Response(200, json={"query": "research internship", "results": [{"url": "https://summer.epfl.ch/apply.html", "snippet": "fake snippet ignored"}]})
        assert str(request.url) == FETCH_ENDPOINT
        assert request.method == "POST"
        body = json.loads(request.content)
        assert body["ttl"] == 0
        assert body["per_url_timeout_ms"] == 25_000
        assert body["format"] == "markdown"
        return httpx.Response(200, json={"results": [{"url": body["urls"][0], "title": "Summer@EPFL", "text": snapshot("epfl.json").text}], "errors": []})
    client = client_with(handler)
    search = client.search("research internship")
    result = client.fetch([search["results"][0]["url"]])
    assert len(calls) == 2
    assert result[0].mode == "live"
    assert result[0].text == snapshot("epfl.json").text
    assert result[0].content_hash
    assert datetime.fromisoformat(result[0].checked_at).tzinfo


@pytest.mark.parametrize("status, expected", [(401, "authentication"), (402, "exhausted"), (429, "rate limit"), (503, "provider returned an error")])
def test_http_errors_are_explicit_without_leaking_provider_body(status, expected):
    client = client_with(lambda request: httpx.Response(status, json={"message": "test-secret-do-not-print and private response"}))
    with pytest.raises(TinyFishError) as captured:
        client.search("research")
    assert expected in str(captured.value)
    assert "test-secret" not in str(captured.value)
    assert "private response" not in str(captured.value)


@pytest.mark.parametrize("error", [httpx.ReadTimeout("private secret"), httpx.ConnectError("private secret")])
def test_transport_failures_are_safe_and_do_not_return_cache(error):
    def handler(request):
        raise error
    result = DiscoverService(client=client_with(handler)).discover("EPFL")
    assert result.mode == "live"
    assert result.errors
    assert not result.opportunities
    assert not result.snapshots
    assert "private secret" not in " ".join(result.errors)


def test_per_url_failure_preserves_successful_snapshots_and_explicit_error():
    original = snapshot("epfl.json")
    def handler(request):
        return httpx.Response(200, json={"results": [{"url": original.url, "text": original.text}], "errors": [{"url": OIST_APPLY, "error": "timeout", "message": "must not leak"}]})
    client = client_with(handler)
    with pytest.raises(TinyFishError) as captured:
        client.fetch([original.url, OIST_APPLY])
    assert len(captured.value.snapshots) == 1
    assert original.url == captured.value.snapshots[0].url
    assert "timeout" in captured.value.errors[0]
    assert OIST_APPLY in captured.value.errors[0]
    assert "must not leak" not in captured.value.errors[0]


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/", "https://localhost/", "http://169.254.169.254/latest/meta-data/",
    "file:///etc/passwd", "https://user:password@example.org/", "https://example.org/login",
    "https://example.org/?token=private", "https://example.org:9000/", "http://[::1]/",
])
def test_private_targets_are_rejected_before_network(url):
    def handler(request):
        pytest.fail("Rejected URL must not reach a provider call")
    with pytest.raises(TinyFishError):
        client_with(handler).fetch([url])
    assert not parse_snapshot(minimal("private body", url))


def test_unsafe_redirect_is_not_source_evidence():
    url = "https://example.org/internships"
    client = client_with(lambda request: httpx.Response(200, json={"results": [{"url": url, "final_url": "http://127.0.0.1/", "text": "sensitive body"}], "errors": []}))
    with pytest.raises(TinyFishError) as captured:
        client.fetch([url])
    assert not captured.value.snapshots
    assert "sensitive body" not in str(captured.value)


@pytest.mark.parametrize("body", [[], {"results": "wrong"}, {"results": [{"url": "https://example.org/", "text": None}], "errors": []}])
def test_malformed_or_empty_provider_content_is_explicit(body):
    client = client_with(lambda request: httpx.Response(200, json=body))
    with pytest.raises(TinyFishError):
        client.fetch(["https://example.org/"])


def test_invalid_json_response_is_safe():
    client = client_with(lambda request: httpx.Response(200, text="<html>provider error private</html>"))
    with pytest.raises(TinyFishError) as captured:
        client.search("internship")
    assert "invalid JSON" in str(captured.value)
    assert "private" not in str(captured.value)


def test_backend_missing_key_reported_without_network():
    def handler(request):
        pytest.fail("No request permitted without configured key")
    result = DiscoverService(client=TinyFishClient(Settings(tinyfish_key=""), transport=httpx.MockTransport(handler))).discover("EPFL")
    assert result.errors == ["TinyFish API key is not configured on the server."]
    assert not result.opportunities


def test_discovery_runs_search_for_arbitrary_query_and_ignores_snippet_facts():
    calls = []
    def handler(request):
        calls.append(request)
        if request.method == "GET":
            assert request.url.params["query"] == "quantum intern official"
            return httpx.Response(200, json={"results": [
                {"url": "https://example.org/login"},
                {"url": "https://unknown.example.org/quantum", "snippet": "Deadline December 31, 2027, 23:59 UTC. No fee."},
            ]})
        body = json.loads(request.content)
        assert body["urls"] == ["https://unknown.example.org/quantum"]
        return httpx.Response(200, json={"results": [{"url": body["urls"][0], "title": "Quantum internship", "text": "This is a public quantum internship page."}], "errors": []})
    result = DiscoverService(client=client_with(handler)).discover("quantum intern official", limit=1)
    assert len(calls) == 2
    assert len(result.opportunities) == 1
    assert result.errors  # Rejected login page remains visible.
    assert fact_map(result.opportunities[0])["application_deadline"].status == "unknown"
    assert fact_map(result.opportunities[0])["fee_amount"].status == "unknown"


def test_examples_keep_original_time_and_support_source():
    result = DiscoverService().load_examples()
    assert result.mode == "cached"
    assert all(op.mode == "cached" for op in result.opportunities)
    assert all(item.mode == "cached" for item in result.snapshots)
    assert {s.checked_at for s in result.snapshots} == {snapshot("epfl.json").checked_at}
    fall = next(op for op in result.opportunities if op.id == "oist-fall-2027")
    assert fact_map(fall)["funding"].source_url.endswith("program-description")
    assert "2,400 JPY" in fact_map(fall)["funding"].excerpt


def test_corrupt_examples_are_reported_not_relabelled_live(tmp_path):
    (tmp_path / "invalid.json").write_text('{"url":"https://example.org/"}')
    result = DiscoverService(snapshot_dir=tmp_path).load_examples()
    assert result.errors
    assert not result.snapshots
    assert result.mode == "cached"


@pytest.mark.parametrize("limit", [0, 7, -1, True])
def test_discovery_limit_is_bounded_before_requests(limit):
    result = DiscoverService().discover("internship", limit=limit)
    assert result.errors == ["Discovery limit must be between 1 and 6."]


def test_support_page_does_not_become_fake_cohort():
    assert parse_snapshot(snapshot("oist_support.json")) == []


def test_refresh_missing_all_cohorts_signals_uncertainty_with_source_url():
    def handler(request):
        body = json.loads(request.content)
        return httpx.Response(200, json={"results": [
            {"url": url, "text": "# Apply to Research Internship\nSchedule unavailable."}
            for url in body["urls"]
        ], "errors": []})
    result = DiscoverService(client=client_with(handler)).refresh(OIST_APPLY)
    assert any(OIST_APPLY in error and "cohort" in error for error in result.errors)
    assert result.opportunities[0].cycle == "unknown"
    outcomes = {outcome.url: outcome for outcome in result.source_outcomes}
    assert outcomes[OIST_APPLY].status == "partial"
    assert outcomes[OIST_APPLY].opportunity_ids == [result.opportunities[0].id]
    assert outcomes[OIST_APPLY].errors
    assert outcomes["https://www.oist.jp/admissions/research-internship/program-description"].status == "success"
    assert outcomes["https://www.oist.jp/admissions/research-internship/program-description"].opportunity_ids == []


def test_fetch_partial_failure_has_structured_per_source_outcomes():
    original = snapshot("epfl.json")
    def handler(request):
        return httpx.Response(200, json={"results": [{"url": original.url, "text": original.text}],
                                       "errors": [{"url": OIST_APPLY, "error": "timeout"}]})
    service = DiscoverService(client=client_with(handler))
    result = service._fetch("source refresh", [original.url, OIST_APPLY])
    outcomes = {outcome.url: outcome for outcome in result.source_outcomes}
    assert outcomes[original.url].status == "success"
    assert outcomes[original.url].opportunity_ids == ["epfl-summer-2027"]
    assert not outcomes[original.url].errors
    assert outcomes[OIST_APPLY].status == "failed"
    assert outcomes[OIST_APPLY].opportunity_ids == []
    assert "timeout" in outcomes[OIST_APPLY].errors[0]
    assert result.opportunities[0].id == "epfl-summer-2027"


def test_no_provider_result_produces_failed_outcome_for_that_source():
    client = client_with(lambda request: httpx.Response(200, json={"results": [], "errors": []}))
    result = DiscoverService(client=client)._fetch("source refresh", [OIST_APPLY])
    assert result.source_outcomes[0].url == OIST_APPLY
    assert result.source_outcomes[0].status == "failed"
    assert result.source_outcomes[0].errors
    assert not result.opportunities


def test_fetch_http_failure_has_failed_outcomes_for_every_requested_source():
    client = client_with(lambda request: httpx.Response(429, json={"message": "private response"}))
    urls = [OIST_APPLY, snapshot("epfl.json").url]
    result = DiscoverService(client=client)._fetch("source refresh", urls)
    assert {outcome.url for outcome in result.source_outcomes} == set(urls)
    assert all(outcome.status == "failed" and outcome.errors for outcome in result.source_outcomes)
    assert "private response" not in json.dumps(result.model_dump())


def test_one_oist_search_result_keeps_both_valid_cohorts_for_ingestion():
    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"results": [{"url": OIST_APPLY}]})
        body = json.loads(request.content)
        return httpx.Response(200, json={"results": [
            {"url": url, "text": snapshot("oist.json" if url == OIST_APPLY else "oist_support.json").text}
            for url in body["urls"]
        ], "errors": []})
    result = DiscoverService(client=client_with(handler)).discover("OIST research internship", limit=1)
    assert {op.id for op in result.opportunities} == {"oist-spring-2027", "oist-fall-2027"}
    outcomes = {outcome.url: outcome for outcome in result.source_outcomes}
    assert outcomes[OIST_APPLY].status == "success"
    assert set(outcomes[OIST_APPLY].opportunity_ids) == {"oist-spring-2027", "oist-fall-2027"}
    support = outcomes["https://www.oist.jp/admissions/research-internship/program-description"]
    assert support.status == "success" and support.opportunity_ids == []


def test_removed_oist_cohort_reports_only_actual_cohorts_without_rollover():
    original = snapshot("oist.json")
    original.text = "\n".join(line for line in original.text.splitlines() if "Fall 2027 Internship" not in line)
    def handler(request):
        return httpx.Response(200, json={"results": [{"url": OIST_APPLY, "text": original.text}], "errors": []})
    result = DiscoverService(client=client_with(handler))._fetch("source refresh", [OIST_APPLY])
    assert result.source_outcomes[0].opportunity_ids == ["oist-spring-2027"]
    assert {op.id for op in result.opportunities} == {"oist-spring-2027"}


def test_redirect_retains_outcome_for_original_requested_url():
    url = "https://public.example.org/previous"
    final_url = "https://public.example.org/current"
    client = client_with(lambda request: httpx.Response(200, json={"results": [{
        "url": url, "final_url": final_url, "text": "Public internship description."
    }], "errors": []}))
    result = DiscoverService(client=client)._fetch("source refresh", [url])
    assert result.source_outcomes[0].url == url
    assert result.source_outcomes[0].status == "success"
    assert result.source_outcomes[0].opportunity_ids == [result.opportunities[0].id]
    assert result.snapshots[0].url == final_url


def test_backend_mitacs_program_rule_does_not_reject_computer_science_field():
    from app.models import GraphContext, ProfileState
    from app.planner import build_plan
    opportunity, = parse_snapshot(snapshot("mitacs.json"))
    plan = build_plan(GraphContext(opportunities=[opportunity]), ProfileState(degree="BTech", field="computer_science"))
    criteria = {item.name: item for item in plan.targets[0].criteria}
    assert criteria["degree_program_types"].status == "met"
    assert all(item.status != "not_met" for item in plan.targets[0].criteria if item.name == "fields")


def test_redirected_success_and_failed_source_outcomes_stay_independent():
    url = "https://public.example.org/old"
    final_url = "https://public.example.org/new"
    client = client_with(lambda request: httpx.Response(200, json={
        "results": [{"url": url, "final_url": final_url, "text": "Public internship."}],
        "errors": [{"url": OIST_APPLY, "error": "bot_blocked"}],
    }))
    result = DiscoverService(client=client)._fetch("source refresh", [url, OIST_APPLY])
    outcomes = {outcome.url: outcome for outcome in result.source_outcomes}
    assert outcomes[url].status == "success"
    assert not outcomes[url].errors
    assert outcomes[OIST_APPLY].status == "failed"
    assert "bot_blocked" in outcomes[OIST_APPLY].errors[0]
    assert result.snapshots[0].url == final_url


def test_malformed_error_code_still_produces_safe_failed_outcome():
    client = client_with(lambda request: httpx.Response(200, json={
        "results": [], "errors": [{"url": OIST_APPLY, "error": ["private body"]}],
    }))
    result = DiscoverService(client=client)._fetch("source refresh", [OIST_APPLY])
    assert result.source_outcomes[0].status == "failed"
    assert "source_failure" in result.source_outcomes[0].errors[0]
    assert "private body" not in json.dumps(result.model_dump())
