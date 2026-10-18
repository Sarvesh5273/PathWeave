from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

from app.config import Settings
from app.discovery.browser import (
    AGENT_ENDPOINT, CACHE_TTL_SECONDS, OUTPUT_SCHEMA, RUN_ENDPOINT,
    BrowserFallback, agent_goal, agent_start_url,
)
from app.discovery.contracts import DiscoveryPreferences, SourceLead
from app.discovery.provider import ProviderError


KEY = "test-key-not-a-real-credential"
RUN = "run_test-123"
PORTAL = SourceLead(url="https://jobs.ashbyhq.com/example", organization="Example", kind="board")
PREFS = DiscoveryPreferences(roles=["Software engineering", "ML"], locations=["United States"], remote_ok=True)
OPENING = {"title": "  Software\nEngineer Intern  ", "location": " San Francisco ",
           "url": "https://jobs.ashbyhq.com/example/job-123#apply"}


def browser(handler, enabled=True, *, verified=True, max_steps=25):
    # Explicit simulated account capability for offline tests, NOT live verification.
    return BrowserFallback(SimpleNamespace(tinyfish_key=KEY, tinyfish_agent_enabled=enabled,
                                          tinyfish_agent_step_cap_verified=verified,
                                          tinyfish_agent_max_steps=max_steps), httpx.MockTransport(handler))


def event(data):
    return ("data: " + json.dumps(data) + "\n\n").encode()


def complete(result=None, status="COMPLETED", **extra):
    return {"type": "COMPLETE", "run_id": RUN, "status": status,
            "result": {"openings": [OPENING]} if result is None else result, **extra}


def response(*events):
    return httpx.Response(200, content=b"".join(event(e) for e in events),
                          headers={"content-type": "text/event-stream"})


def test_agent_sse_rest_body_and_typed_normalized_leads():
    def handler(request):
        assert request.method == "POST" and str(request.url) == AGENT_ENDPOINT
        assert request.headers["X-API-Key"] == KEY
        assert request.headers["Accept"] == "text/event-stream"
        payload = json.loads(request.content)
        assert payload["url"] == PORTAL.url + "?employmentType=Intern"
        assert payload["agent_config"] == {"max_duration_seconds": 120, "max_steps": 25}
        assert payload["output_schema"] == OUTPUT_SCHEMA
        assert payload["use_profile"] is False and payload["use_vault"] is False
        assert "mode" not in payload["agent_config"]
        assert "already lists only internships" in payload["goal"]
        assert "Do not use the search box or filters" in payload["goal"]
        return response({"type": "STARTED", "run_id": RUN}, {"type": "HEARTBEAT"}, complete())
    b = browser(handler)
    lead, = b.find(PORTAL, PREFS)
    assert lead.title == "Software Engineer Intern" and lead.location == "San Francisco"
    assert lead.url == OPENING["url"].split("#")[0]
    assert lead.source_url == PORTAL.url and lead.organization == "Example"
    assert lead.kind == "posting" and lead.via == "agent"
    assert b.last_run_id == RUN and b.last_status == "COMPLETED"


def test_verified_provider_default_limit_uses_no_beta_field():
    def handler(request):
        payload=json.loads(request.content)
        assert payload["agent_config"]=={"max_duration_seconds":120}
        return response(complete())
    config=SimpleNamespace(tinyfish_key=KEY,tinyfish_agent_enabled=True,tinyfish_agent_step_cap_verified=False,
                           tinyfish_agent_default_cap_verified=True,tinyfish_agent_max_steps=150)
    result=BrowserFallback(config,httpx.MockTransport(handler)).find(PORTAL,PREFS)
    assert result


@pytest.mark.parametrize("steps",[25,149,151,0])
def test_provider_default_cap_cannot_be_used_for_other_step_budgets(steps):
    config=SimpleNamespace(tinyfish_key=KEY,tinyfish_agent_enabled=True,tinyfish_agent_step_cap_verified=False,
                           tinyfish_agent_default_cap_verified=True,tinyfish_agent_max_steps=steps)
    with pytest.raises(ProviderError,match="step cap"):
        BrowserFallback(config,httpx.MockTransport(lambda request:pytest.fail("Unverified request"))).find(PORTAL,PREFS)


def test_goal_preserves_levels_whole_list_roles_and_location_rules():
    p = PREFS.model_copy(update={"seniority": ["new_grad", "entry_level"]})
    goal = agent_goal(p, "Example")
    for phrase in ["new-grad roles or entry-level roles", 'type "new grad"', "not just the first screen",
                   "scroll to the bottom", "Do not use location or team filters", "Software engineering", "ML",
                   "United States, or remote", "San Francisco counts", "Do not sign in, apply, or submit any form",
                   "bypassing a protection", "up to 8", "whole list fits"]:
        assert phrase in goal
    experienced = p.model_copy(update={"seniority": ["experienced"]})
    assert 'type "Software engineering"' in agent_goal(experienced, "Example")


def test_ashby_prefilter_only_on_actual_internship_only_boards_preserves_query():
    assert agent_start_url(PORTAL.url + "?team=Engineering&employmentType=FullTime", PREFS) == PORTAL.url + "?team=Engineering&employmentType=Intern"
    for url in [PORTAL.url + "/posting", "https://jobs.ashbyhq.com.evil.org/example", "https://example.org/careers"]:
        assert agent_start_url(url, PREFS) == url
    mixed = PREFS.model_copy(update={"seniority": ["internship", "new_grad"]})
    assert agent_start_url(PORTAL.url, mixed) == PORTAL.url


def test_goal_versioned_cache_key_is_stable_and_changes_for_goal_inputs():
    b = browser(lambda _: pytest.fail("Cache key must not call provider"))
    key = b.cache_key(PORTAL, PREFS)
    assert len(key) == 40 and b.cache_key(PORTAL, PREFS) == key
    assert CACHE_TTL_SECONDS == 86_400
    for update in [{"roles": ["Design"]}, {"seniority": ["new_grad"]}, {"locations": ["India"]}, {"remote_ok": False}]:
        assert b.cache_key(PORTAL, PREFS.model_copy(update=update)) != key
    assert b.cache_key(PORTAL.model_copy(update={"organization": "Other"}), PREFS) != key


def test_disabled_or_unsafe_targets_never_start_a_metered_run():
    def forbidden(_):
        pytest.fail("Unexpected metered call")
    with pytest.raises(ProviderError, match="not enabled"):
        browser(forbidden, False).find(PORTAL, PREFS)
    b = BrowserFallback(SimpleNamespace(tinyfish_key=KEY), httpx.MockTransport(forbidden))
    with pytest.raises(ProviderError, match="not enabled"):
        b.find(PORTAL, PREFS)
    for url in ["http://127.0.0.1/", "https://example.org/login", "https://example.org/?session=secret"]:
        with pytest.raises(ProviderError, match="public portal"):
            browser(forbidden).find(PORTAL.model_copy(update={"url": url}), PREFS)


def test_agent_link_safety_deduplication_and_nested_titles_do_not_trigger_failure_signal():
    rows = [OPENING, OPENING, {"title": "Blocked Content Engineer Intern", "url": "https://example.org/job/2"},
            {"title": "Unsafe", "url": "http://localhost/job"},
            {"title": "Login", "url": "https://example.org/login"},
            {"title": "Private", "url": "https://user:password@example.org/job"},
            {"title": "Portal not opening", "url": PORTAL.url}, {"title": " ", "url": "https://example.org/job/3"}]
    leads = browser(lambda _: response(complete({"openings": rows}))).find(PORTAL, PREFS)
    assert len(leads) == 2 and leads[1].title == "Blocked Content Engineer Intern"


@pytest.mark.parametrize("result", [
    {"openings": [], "success": False, "failure_reason": KEY},
    {"openings": [], "message": "CAPTCHA blocked the page " + KEY},
    {"openings": [], "message": "Access denied"},
    {"openings": [], "message": "login required"},
])
def test_blocked_success_is_an_error_not_no_matches(result):
    with pytest.raises(ProviderError) as raised:
        browser(lambda _: response(complete(result))).find(PORTAL, PREFS)
    assert raised.value.run_id == RUN and raised.value.status == "BLOCKED_CONTENT"
    assert KEY not in str(raised.value)


@pytest.mark.parametrize("result", [{}, {"openings": "not a list"}, {"openings": [{"title": 3, "url": 5}]},
                                    {"openings": [OPENING] * 9}])
def test_agent_result_schema_is_locally_validated(result):
    with pytest.raises(ProviderError) as raised:
        browser(lambda _: response(complete(result))).find(PORTAL, PREFS)
    assert raised.value.status == "INVALID_RESULT" and raised.value.run_id == RUN


def test_empty_success_is_valid_and_legacy_result_json_is_supported():
    assert browser(lambda _: response(complete({"openings": []}))).find(PORTAL, PREFS) == []
    e = complete()
    e["resultJson"] = e.pop("result")
    assert len(browser(lambda _: response(e)).find(PORTAL, PREFS)) == 1


@pytest.mark.parametrize("status", ["FAILED", "CANCELLED"])
def test_terminal_failures_preserve_run_id_without_retry_or_cancel(status):
    calls = []
    def handler(request):
        calls.append(request)
        return response(complete(status=status, error={"message": KEY, "code": "SITE_BLOCKED"}))
    with pytest.raises(ProviderError) as raised:
        browser(handler).find(PORTAL, PREFS)
    assert len(calls) == 1 and raised.value.run_id == RUN
    assert raised.value.status == status and not raised.value.recoverable
    assert KEY not in str(raised.value)


def test_no_terminal_event_preserves_run_id_and_read_only_recovery_gets_leads():
    calls = []
    def handler(request):
        calls.append(request)
        if request.method == "POST":
            return response({"type": "STARTED", "run_id": RUN}, {"type": "PROGRESS", "run_id": RUN})
        assert str(request.url) == f"{RUN_ENDPOINT}/{RUN}"
        return httpx.Response(200, json={"run_id": RUN, "status": "COMPLETED", "result": {"openings": [OPENING]},
                                        "num_of_steps": 5, "goal": KEY, "streaming_url": "https://private.example.org/token"})
    b = browser(handler)
    with pytest.raises(ProviderError) as raised:
        b.find(PORTAL, PREFS)
    assert raised.value.status == "NO_COMPLETE_EVENT"
    assert raised.value.run_id == RUN and raised.value.recoverable
    assert len(b.recover(RUN, PORTAL)) == 1
    assert [call.method for call in calls] == ["POST", "GET"]


class TimeoutStream(httpx.SyncByteStream):
    def __iter__(self):
        yield event({"type": "STARTED", "run_id": RUN})
        raise httpx.ReadTimeout(KEY)


def test_sse_timeout_after_started_retains_run_id_and_never_retries():
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, stream=TimeoutStream())
    b = browser(handler)
    with pytest.raises(ProviderError) as raised:
        b.find(PORTAL, PREFS)
    assert raised.value.run_id == RUN and raised.value.status == "TIMEOUT" and raised.value.recoverable
    assert KEY not in str(raised.value) and len(calls) == 1
    assert b.last_run_id == RUN


@pytest.mark.parametrize("status", ["PENDING", "RUNNING", "FAILED", "CANCELLED"])
def test_recovery_pending_or_failed_is_not_a_new_run_and_does_not_require_enabled_flag(status):
    calls = []
    def handler(request):
        calls.append(request)
        assert request.method == "GET"
        return httpx.Response(200, json={"run_id": RUN, "status": status, "error": {"message": KEY}})
    b = browser(handler, enabled=False)
    with pytest.raises(ProviderError) as raised:
        b.recover(RUN, PORTAL)
    assert raised.value.status == status and raised.value.run_id == RUN
    assert raised.value.recoverable == (status in {"PENDING", "RUNNING"})
    assert KEY not in str(raised.value) and len(calls) == 1


def test_recovery_get_exposes_only_safe_fields_and_validates_id():
    b = browser(lambda _: httpx.Response(200, json={"run_id": RUN, "status": "RUNNING", "goal": KEY,
                                                   "error": {"message": KEY}, "num_of_steps": 4}))
    assert b.get_run(RUN) == {"run_id": RUN, "status": "RUNNING", "result": None, "num_of_steps": 4}
    with pytest.raises(ProviderError):
        b.get_run("../../private?token=" + KEY)


@pytest.mark.parametrize("status", [401, 402, 403, 429, 500])
def test_agent_http_errors_preserve_optional_run_id_and_do_not_echo_body(status):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"run_id": RUN, "message": KEY})
    with pytest.raises(ProviderError) as raised:
        browser(handler).find(PORTAL, PREFS)
    assert raised.value.run_id == RUN and raised.value.status == f"HTTP_{status}"
    assert KEY not in str(raised.value) and len(calls) == 1


def test_multiline_sse_crlf_comments_and_final_frame_without_blank_line():
    body = ': keepalive\r\nevent: message\r\ndata: {"type":"STARTED",\r\ndata: "run_id":"' + RUN + '"}\r\n\r\n'
    body += "data: " + json.dumps(complete())
    assert len(browser(lambda _: httpx.Response(200, text=body)).find(PORTAL, PREFS)) == 1


def test_malformed_sse_after_started_retains_recovery_id():
    b = browser(lambda _: httpx.Response(200, content=event({"type": "STARTED", "run_id": RUN}) + b"data: invalid secret\n\n"))
    with pytest.raises(ProviderError) as raised:
        b.find(PORTAL, PREFS)
    assert raised.value.run_id == RUN and raised.value.recoverable
    assert "secret" not in str(raised.value)


def test_inconsistent_stream_ids_keep_original_run_for_recovery():
    b = browser(lambda _: response({"type": "STARTED", "run_id": RUN}, complete(run_id="different-run")))
    with pytest.raises(ProviderError) as raised:
        b.find(PORTAL, PREFS)
    assert raised.value.run_id == RUN and raised.value.recoverable


@pytest.mark.parametrize("status", [None, "RUNNING", {"unexpected": "object"}])
def test_malformed_terminal_status_keeps_recovery_id(status):
    with pytest.raises(ProviderError) as raised:
        browser(lambda _: response(complete(status=status))).find(PORTAL, PREFS)
    assert raised.value.run_id == RUN and raised.value.status == "UNKNOWN" and raised.value.recoverable


def test_agent_json_instead_of_sse_preserves_run_id():
    with pytest.raises(ProviderError) as raised:
        browser(lambda _: httpx.Response(200, json={"run_id": RUN, "message": KEY})).find(PORTAL, PREFS)
    assert raised.value.run_id == RUN and raised.value.recoverable and KEY not in str(raised.value)


def test_recovery_http_failure_keeps_existing_run_id():
    with pytest.raises(ProviderError) as raised:
        browser(lambda _: httpx.Response(503, text=KEY)).get_run(RUN)
    assert raised.value.run_id == RUN and raised.value.recoverable and raised.value.status == "HTTP_503"
    assert KEY not in str(raised.value)


def test_recovery_rejects_mismatched_ids_and_malformed_status():
    for data in [{"run_id": "wrong-run", "status": "COMPLETED"}, {"run_id": RUN, "status": {"bad": True}}]:
        with pytest.raises(ProviderError) as raised:
            browser(lambda _: httpx.Response(200, json=data)).get_run(RUN)
        assert raised.value.run_id == RUN and raised.value.recoverable


def test_local_stream_deadline_keeps_started_run_id(monkeypatch):
    times = iter([0, 0, 0, 211])
    monkeypatch.setattr("app.discovery.browser.time.monotonic", lambda: next(times))
    with pytest.raises(ProviderError) as raised:
        browser(lambda _: response({"type": "STARTED", "run_id": RUN}, complete())).find(PORTAL, PREFS)
    assert raised.value.run_id == RUN and raised.value.status == "TIMEOUT" and raised.value.recoverable


def test_stream_size_limit_keeps_started_run_id(monkeypatch):
    monkeypatch.setattr("app.discovery.browser.MAX_STREAM_BYTES", 150)
    with pytest.raises(ProviderError) as raised:
        browser(lambda _: response({"type": "STARTED", "run_id": RUN}, {"type": "PROGRESS", "purpose": "x" * 200})).find(PORTAL, PREFS)
    assert raised.value.run_id == RUN and raised.value.status == "CONTENT_TOO_LARGE" and raised.value.recoverable


def test_completed_stream_without_run_id_is_not_silently_accepted():
    e = complete()
    e.pop("run_id")
    with pytest.raises(ProviderError) as raised:
        browser(lambda _: response(e)).find(PORTAL, PREFS)
    assert raised.value.run_id is None and raised.value.status == "INVALID_RESPONSE"


def test_get_run_sanitizes_protected_opening_urls_before_exposing_results():
    b = browser(lambda _: httpx.Response(200, json={
        "run_id": RUN, "status": "COMPLETED", "result": {"openings": [OPENING, {
            "title": "Private job", "url": "https://user:password@example.org/login",
        }]},
    }))
    data = b.get_run(RUN)
    assert data["result"] == {"openings": [{"title": "Software Engineer Intern", "location": "San Francisco",
                                           "url": OPENING["url"].split("#")[0]}]}


@pytest.mark.parametrize("verified,max_steps", [
    (False, 25), (None, 25), ("true", 25),
    (True, 0), (True, -1), (True, 501), (True, True), (True, "25"), (True, 25.0), (True, None),
])
def test_enabled_agent_fails_closed_without_verified_integer_step_cap(verified, max_steps):
    def forbidden(_):
        pytest.fail("Unverified or invalid step cap must not start a run")
    with pytest.raises(ProviderError) as raised:
        browser(forbidden, verified=verified, max_steps=max_steps).find(PORTAL, PREFS)
    assert raised.value.status == "STEP_CAP_UNVERIFIED" and raised.value.run_id is None


def test_real_settings_type_fails_closed_when_cap_is_not_verified():
    settings = Settings(tinyfish_key=KEY, tinyfish_agent_enabled=True,
                        tinyfish_agent_step_cap_verified=False, tinyfish_agent_max_steps=25)
    b = BrowserFallback(settings, httpx.MockTransport(lambda _: pytest.fail("No metered call authorized")))
    with pytest.raises(ProviderError, match="verified account-supported step cap"):
        b.find(PORTAL, PREFS)


def test_missing_step_cap_settings_fail_closed_even_with_mock_transport():
    b = BrowserFallback(SimpleNamespace(tinyfish_key=KEY, tinyfish_agent_enabled=True),
                        httpx.MockTransport(lambda _: pytest.fail("Mock transport does not imply verification")))
    with pytest.raises(ProviderError) as raised:
        b.find(PORTAL, PREFS)
    assert raised.value.status == "STEP_CAP_UNVERIFIED"


@pytest.mark.parametrize("max_steps", [1, 25, 500])
def test_verified_step_cap_is_transmitted_exactly(max_steps):
    def handler(request):
        assert json.loads(request.content)["agent_config"] == {"max_steps": max_steps, "max_duration_seconds": 120}
        return response(complete({"openings": []}))
    assert browser(handler, max_steps=max_steps).find(PORTAL, PREFS) == []


def test_disabled_agent_stays_disabled_even_with_valid_step_cap():
    with pytest.raises(ProviderError) as raised:
        browser(lambda _: pytest.fail("Disabled Agent must not run"), enabled=False).find(PORTAL, PREFS)
    assert raised.value.status == "DISABLED"


def test_beta_403_never_retries_without_max_steps():
    calls = []
    def handler(request):
        calls.append(request)
        assert json.loads(request.content)["agent_config"]["max_steps"] == 25
        return httpx.Response(403, json={"error": {"code": "FORBIDDEN", "message": "not enabled for custom max steps " + KEY}})
    with pytest.raises(ProviderError) as raised:
        browser(handler).find(PORTAL, PREFS)
    assert len(calls) == 1 and raised.value.status == "HTTP_403"
    assert raised.value.run_id is None and KEY not in str(raised.value)


def test_on_started_persists_immediately_before_next_event_and_only_once():
    persisted = []
    class LifecycleStream(httpx.SyncByteStream):
        def __iter__(self):
            assert persisted == []
            yield event({"type": "STARTED", "run_id": RUN})
            assert persisted == [RUN]
            yield event({"type": "STARTED", "run_id": RUN})
            yield event({"type": "PROGRESS", "run_id": RUN, "purpose": "Reading"})
            yield event(complete())
    b = browser(lambda _: httpx.Response(200, stream=LifecycleStream()))
    assert len(b.find(PORTAL, PREFS, on_started=persisted.append)) == 1
    assert persisted == [RUN]


def test_on_started_is_called_before_stream_timeout():
    persisted = []
    b = browser(lambda _: httpx.Response(200, stream=TimeoutStream()))
    with pytest.raises(ProviderError) as raised:
        b.find(PORTAL, PREFS, on_started=persisted.append)
    assert persisted == [RUN] and raised.value.run_id == RUN
    assert raised.value.status == "TIMEOUT" and raised.value.recoverable


def test_failed_persistence_callback_preserves_run_id_and_never_retries_or_cancels():
    calls = []
    def handler(request):
        calls.append(request)
        return response({"type": "STARTED", "run_id": RUN}, complete())
    def fail_persistence(run_id):
        assert run_id == RUN
        raise RuntimeError(KEY)
    b = browser(handler)
    with pytest.raises(ProviderError) as raised:
        b.find(PORTAL, PREFS, on_started=fail_persistence)
    assert raised.value.status == "PERSISTENCE_FAILED" and raised.value.run_id == RUN
    assert raised.value.recoverable and KEY not in str(raised.value)
    assert len(calls) == 1 and b.last_run_id == RUN


def test_on_started_receives_first_id_even_if_started_event_is_missing():
    persisted = []
    b = browser(lambda _: response(complete()))
    assert len(b.find(PORTAL, PREFS, on_started=persisted.append)) == 1
    assert persisted == [RUN]


def test_on_started_retains_http_error_run_id_before_raising():
    persisted = []
    b = browser(lambda _: httpx.Response(403, json={"run_id": RUN, "error": {"message": KEY}}))
    with pytest.raises(ProviderError) as raised:
        b.find(PORTAL, PREFS, on_started=persisted.append)
    assert persisted == [RUN] and raised.value.run_id == RUN and raised.value.status == "HTTP_403"


@pytest.mark.parametrize("url", ["https://example.org/profile/person", "https://example.org/profiles/person",
                                 "https://example.org/careers?email=person%40example.org",
                                 "https://example.org/careers#email=person%40example.org"])
def test_agent_private_profile_or_personal_query_does_not_start_a_run(url):
    with pytest.raises(ProviderError) as raised:
        browser(lambda _: pytest.fail("Private portal must be rejected")).find(PORTAL.model_copy(update={"url": url}), PREFS)
    assert raised.value.status == "INVALID_URL"
