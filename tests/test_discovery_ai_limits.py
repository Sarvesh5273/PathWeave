"""Offline admission tests; no provider/network credentials or live calls."""
from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic import BaseModel, Field

import app.discovery.ai as ai
from app.discovery.contracts import DiscoveryPreferences, WebPage
from app.discovery.extract import ListingExtractor
from app.models import SourceSnapshot


class Output(BaseModel):
    title: str = Field(description="Verbose documentation should not cost tokens")


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    state = SimpleNamespace(now=0.0, waits=[])
    monkeypatch.setattr(ai, "_GUARDS", {})
    monkeypatch.setattr(ai, "monotonic", lambda: state.now)

    def sleep(seconds):
        assert seconds >= 0
        state.waits.append(seconds)
        state.now += seconds

    monkeypatch.setattr(ai, "sleep", sleep)
    return state


def settings(**updates):
    return SimpleNamespace(**{"groq_key": "offline-mock-key", "groq_model": "offline-model", **updates})


def completion(content=None, *, usage=None, headers=None, finish="stop"):
    envelope = {"choices": [{"finish_reason": finish, "message": {"content": json.dumps(content or {"title": "complete"})}}]}
    if usage is not None:
        envelope["usage"] = usage
    return httpx.Response(200, json=envelope, headers=headers)


def call(config, transport, **options):
    return ai.structured_call(config, Output, system="Return JSON.", user="public source", transport=transport, **options)


def source(i, text=None):
    return WebPage(snapshot=SourceSnapshot(id=f"source-{i}", url=f"https://lab.example.org/jobs/{i}", title=f"Software Intern {i}",
        text=text or f"Software Intern {i} at Aurora Lab\nBasic qualifications:\nPython is required.", checked_at="2026-10-16T12:00:00+00:00"),
        requested_url=f"https://lab.example.org/jobs/{i}")


def extraction(i, **updates):
    output = {"page_type": "posting", "listings": [{"title": f"Software Intern {i}", "organization": "Aurora Lab", "seniority": "internship", "requirements": [
        {"name": "skills", "value": ["python"], "kind": "requirement", "excerpt": "Python is required."},
    ]}], "extraction_complete": True}
    output.update(updates)
    return output


def test_multiple_successive_pages_use_shared_default_input_and_output_admission(clock):
    config = settings()  # Actual defaults, not the large legacy-test throughput cap.
    calls, attempts = [], []
    used = 0
    reset_at = 60.0

    def handler(request):
        nonlocal used, reset_at
        if clock.now >= reset_at:
            used, reset_at = 0, clock.now + 60
        body = json.loads(request.content)
        assert body["max_completion_tokens"] == 900
        assert 1800 <= 8000 - used
        i = len(calls)
        calls.append(clock.now)
        used += 2000
        return completion(extraction(i), usage={"prompt_tokens": 1800, "completion_tokens": 200, "total_tokens": 2000},
            headers={"x-ratelimit-limit-tokens": "8000", "x-ratelimit-remaining-tokens": str(8000 - used), "x-ratelimit-reset-tokens": f"{reset_at - clock.now}s"})

    transport = httpx.MockTransport(handler)
    # Distinct extractor instances share the same credential/model admission.
    results = [ListingExtractor(config, transport).extract(source(i), DiscoveryPreferences(roles=["software engineer"]), remaining_seconds=130 - clock.now,
        on_call=lambda: attempts.append(1)) for i in range(3)]
    assert [len(result.listings) for result in results] == [1, 1, 1]
    assert all(result.listings[0].requirements[0].excerpt == "Python is required." for result in results)
    assert len(attempts) == len(calls) == 3
    # Actual 200 output + next reservation 900 > the separate 1000 ceiling,
    # despite ample input remaining. One bounded wait per subsequent page.
    assert calls[0] == 0 and calls[1] >= 60 and calls[2] >= 120
    assert len(clock.waits) == 2 and all(60 <= seconds <= 65 for seconds in clock.waits)


def test_shared_extraction_admission_refuses_wait_past_absolute_deadline(clock):
    requests, attempts = [], []

    def handler(request):
        requests.append(request)
        return completion(extraction(0), headers={"x-ratelimit-remaining-tokens": "0", "x-ratelimit-reset-tokens": "1m"}, usage={"total_tokens": 2000})

    extractor = ListingExtractor(settings(), httpx.MockTransport(handler))
    first = extractor.extract(source(0), DiscoveryPreferences(roles=["software"]), remaining_seconds=5, on_call=lambda: attempts.append(1))
    second = extractor.extract(source(1), DiscoveryPreferences(roles=["software"]), remaining_seconds=5, on_call=lambda: attempts.append(1))
    assert first.listings and not second.listings
    assert "time budget" in second.warnings[-1] and "[AI:rate_limit]" in second.warnings[-1]
    assert not ai.ai_warning_is_fatal(second.warnings[-1])
    assert len(requests) == len(attempts) == 1 and not clock.waits


def test_long_matching_inputs_are_repacked_locally_then_ai_scored_without_losing_ids(clock):
    from app.discovery.contracts import DiscoveryListing
    from app.discovery.ranking import rank_listings
    calls, attempts = [], []
    listings = [DiscoveryListing(id=str(i), title="Software Engineer Intern", organization="Aurora Lab", seniority="internship", call_status="open",
        summary="Software engineering research. " * 15, eligibility="Applicants must review all source eligibility conditions. " * 12,
        source_url=f"https://lab.example.org/jobs/{i}", apply_url=f"https://lab.example.org/jobs/{i}", checked_at="2026-10-16T12:00:00+00:00") for i in range(20)]

    def handler(request):
        body = json.loads(request.content)
        items = json.loads(body["messages"][1]["content"])["openings"]
        calls.append([item["id"] for item in items])
        assert len(items) < 20
        return completion({"verdicts": [{"id": item["id"], "role_fit": "strong", "location_fit": "match", "eligibility_fit": "unknown", "reason": "Software engineering internship"} for item in items]},
            usage={"prompt_tokens": 1500, "completion_tokens": 700, "total_tokens": 2200})

    rows = rank_listings(DiscoveryPreferences(roles=["software engineer"]), listings,
        settings(discovery_ai_tpm=6000, discovery_ai_max_output_tokens=2500, discovery_ai_output_tpm=10_000), httpx.MockTransport(handler), remaining_seconds=180,
        on_call=lambda: attempts.append(1))
    assert len(rows) == 20
    assert [i for batch in calls for i in batch] == list(range(20))
    assert len(attempts) == len(calls) == 2
    assert all(any("AI fit" in reason for reason in row.reasons) for row in rows)
    assert not clock.waits


def test_actual_usage_replaces_worst_case_reservation_instead_of_waiting_unnecessarily(clock):
    config = settings(discovery_ai_tpm=3000, discovery_ai_max_output_tokens=1200, discovery_ai_output_tpm=10_000)
    requests = []

    def handler(request):
        requests.append(request)
        return completion(usage={"prompt_tokens": 200, "completion_tokens": 200, "total_tokens": 400})

    transport = httpx.MockTransport(handler)
    for _ in range(2):
        ai.structured_call(config, Output, system="JSON", user="x" * 3000, transport=transport)
    assert len(requests) == 2 and not clock.waits
    guard = ai._guard_for(config.groq_key, config.groq_model)
    assert sum(charge.tokens for charge in guard.charges) == 400
    assert sum(charge.output_tokens for charge in guard.charges) == 400


def test_missing_usage_keeps_conservative_reservation_across_new_instances(clock):
    config = settings(discovery_ai_tpm=1500, discovery_ai_max_output_tokens=1200, discovery_ai_output_tpm=10_000)
    transport = httpx.MockTransport(lambda request: completion())
    for _ in range(2):
        ai.structured_call(config, Output, system="JSON", user="x" * 3000, transport=transport, remaining_seconds=70)
    assert len(clock.waits) == 1 and 60 <= clock.waits[0] <= 65


def test_external_account_token_headers_force_pacing_even_with_small_local_usage(clock):
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        return completion(usage={"total_tokens": 50}, headers={"x-ratelimit-remaining-tokens": "0", "x-ratelimit-reset-tokens": "2.5s"} if count == 1 else {})

    config, transport = settings(discovery_ai_output_tpm=10_000), httpx.MockTransport(handler)
    call(config, transport)
    call(config, transport, remaining_seconds=5)
    assert count == 2 and len(clock.waits) == 1 and 2.5 < clock.waits[0] < 2.6


def test_request_rate_headers_are_independent_of_token_headers(clock):
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        return completion(usage={"total_tokens": 50}, headers={"x-ratelimit-remaining-requests": "0", "x-ratelimit-reset-requests": "1s"} if count == 1 else {})

    config, transport = settings(discovery_ai_output_tpm=10_000), httpx.MockTransport(handler)
    call(config, transport)
    call(config, transport, remaining_seconds=5)
    assert count == 2 and len(clock.waits) == 1


@pytest.mark.parametrize("headers", [{"retry-after": "0.2"}, {"x-ratelimit-remaining-tokens": "0", "x-ratelimit-reset-tokens": "200ms"}])
def test_one_header_backed_429_wait_and_retry_counts_both_actual_attempts(clock, headers):
    requests, attempts = [], []

    def handler(request):
        requests.append(clock.now)
        return httpx.Response(429, headers=headers, json={"error": "private mock provider body"}) if len(requests) == 1 else completion()

    output = call(settings(), httpx.MockTransport(handler), remaining_seconds=5, on_call=lambda: attempts.append(1))
    assert output.title == "complete"
    assert len(requests) == len(attempts) == 2 and len(clock.waits) == 1
    assert requests[1] >= .2


def test_second_429_is_not_retried_again_and_preserves_safe_metadata(clock):
    attempts = []
    transport = httpx.MockTransport(lambda request: httpx.Response(429, headers={"retry-after": "1"}, text="secret body"))
    with pytest.raises(ai.AIError) as raised:
        call(settings(), transport, remaining_seconds=10, on_call=lambda: attempts.append(1))
    error = raised.value
    assert error.status == 429 and error.retry_after == 1 and error.code == "rate_limit" and not error.fatal
    assert len(attempts) == 2 and len(clock.waits) == 1
    assert "secret" not in str(error)


def test_wait_already_used_for_admission_prevents_an_additional_429_retry(clock):
    requests = []

    def handler(request):
        requests.append(request)
        if len(requests) == 1:
            return completion(usage={"total_tokens": 20}, headers={"x-ratelimit-remaining-tokens": "0", "x-ratelimit-reset-tokens": "1s"})
        return httpx.Response(429, headers={"retry-after": "1"})

    config, transport = settings(discovery_ai_output_tpm=10_000), httpx.MockTransport(handler)
    call(config, transport)
    with pytest.raises(ai.AIError, match="rate limit"):
        call(config, transport, remaining_seconds=10)
    assert len(requests) == 2 and len(clock.waits) == 1


@pytest.mark.parametrize("headers", [{}, {"retry-after": "secret body"}, {"retry-after": "NaN"}, {"retry-after": "-1", "x-ratelimit-reset-tokens": "bad"}])
def test_429_without_safe_reset_headers_never_blindly_retries(clock, headers):
    attempts = []
    with pytest.raises(ai.AIError) as raised:
        call(settings(), httpx.MockTransport(lambda request: httpx.Response(429, headers=headers, text="sensitive")), on_call=lambda: attempts.append(1))
    assert raised.value.status == 429 and raised.value.retry_after is None
    assert len(attempts) == 1 and not clock.waits
    assert "sensitive" not in str(raised.value) and "secret body" not in str(raised.value)


@pytest.mark.parametrize("remaining,max_wait", [(1, 65), (120, 2)])
def test_header_backed_retry_must_fit_both_run_deadline_and_wait_limit(clock, remaining, max_wait):
    attempts = []
    with pytest.raises(ai.AIError, match="time budget") as raised:
        call(settings(discovery_ai_max_wait_seconds=max_wait), httpx.MockTransport(lambda request: httpx.Response(429, headers={"retry-after": "3"})),
            remaining_seconds=remaining, on_call=lambda: attempts.append(1))
    assert raised.value.code == "rate_limit" and len(attempts) == 1 and not clock.waits


@pytest.mark.parametrize("status,code,fatal", [(400, "request", True), (401, "authentication", True), (402, "quota", True), (403, "denied", True), (503, "provider", False)])
def test_auth_quota_request_and_transient_errors_have_distinct_sanitized_categories(clock, status, code, fatal):
    attempts = []
    with pytest.raises(ai.AIError) as raised:
        call(settings(), httpx.MockTransport(lambda request: httpx.Response(status, text="offline-mock-key private response")), on_call=lambda: attempts.append(1))
    error = raised.value
    assert error.status == status and error.code == code and error.fatal is fatal
    assert ai.ai_warning_is_fatal(str(error)) is fatal
    assert len(attempts) == 1 and not clock.waits
    assert "offline-mock-key" not in str(error) and "private response" not in str(error)


def test_malformed_response_is_not_a_permanent_provider_stop(clock):
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        return httpx.Response(200, json={"choices": [{"message": {"content": "bad JSON"}}]}) if count == 1 else completion()

    config, transport = settings(discovery_ai_output_tpm=10_000), httpx.MockTransport(handler)
    with pytest.raises(ai.AIError) as raised:
        call(config, transport)
    assert raised.value.code == "invalid_response" and not raised.value.fatal
    assert call(config, transport).title == "complete"
    assert count == 2


@pytest.mark.parametrize("finish,complete", [("length", True), ("stop", False)])
def test_output_exhaustion_and_declared_partial_requirements_are_explicit_not_accepted(clock, finish, complete):
    result = ListingExtractor(settings(discovery_ai_max_output_tokens=1200, discovery_ai_output_tpm=10_000), httpx.MockTransport(lambda request: completion(
        extraction(0, extraction_complete=complete), finish=finish))).extract(source(0), DiscoveryPreferences(roles=["software"]))
    assert not result.listings and "incomplete" in result.warnings[-1]
    assert "[AI:incomplete]" in result.warnings[-1] and not ai.ai_warning_is_fatal(result.warnings[-1])


def test_missing_completeness_flag_cannot_silently_accept_partial_requirements(clock):
    output = extraction(0)
    del output["extraction_complete"]
    result = ListingExtractor(settings(), httpx.MockTransport(lambda request: completion(output))).extract(source(0), DiscoveryPreferences(roles=["software"]))
    assert not result.listings
    assert "[AI:invalid_response]" in result.warnings[-1] and not ai.ai_warning_is_fatal(result.warnings[-1])


def test_schema_metadata_is_compact_but_named_fields_enums_and_validation_survive(clock):
    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        schema = json.loads(body["messages"][0]["content"].split("matching this schema:\n", 1)[1])
        assert schema["properties"]["title"] == {"type": "string"}
        assert schema["required"] == ["title"] and "title" not in schema
        assert "Verbose documentation" not in body["messages"][0]["content"]
        assert body["max_completion_tokens"] == 1200
        return completion()

    assert call(settings(discovery_ai_max_output_tokens=1200, discovery_ai_output_tpm=10_000), httpx.MockTransport(handler)).title == "complete"
    assert len(requests) == 1


def test_oversized_token_admission_never_makes_a_request_or_silently_shrinks_output(clock):
    def forbidden(*args):
        pytest.fail("Oversized reservation must not reach HTTP or usage callback")

    with pytest.raises(ai.AIError) as raised:
        ai.structured_call(settings(discovery_ai_tpm=1000, discovery_ai_max_output_tokens=900), Output,
            system="JSON", user="x" * 4000, transport=httpx.MockTransport(forbidden), on_call=forbidden)
    assert raised.value.code == "input_limit" and not raised.value.fatal and not clock.waits


def test_shared_slot_acquisition_is_bounded_and_does_not_count_unmade_http(clock):
    config = settings()
    guard = ai._guard_for(config.groq_key, config.groq_model)
    guard.lock.acquire()
    try:
        with pytest.raises(ai.AIError, match="admission slot"):
            call(config, httpx.MockTransport(lambda request: pytest.fail("No admitted slot")), remaining_seconds=.001,
                on_call=lambda: pytest.fail("No HTTP attempt"))
    finally:
        guard.lock.release()


@pytest.mark.parametrize("header,expected", [("1m2.5s", 62.5), ("500ms", .5), ("1h", 3600), ("-1s", None), ("inf", None), ("provider secret", None)])
def test_reset_header_duration_parser_is_strict(header, expected):
    assert ai._duration(header) == expected


FULL_INPUT_HEADERS = {
    "x-ratelimit-limit-tokens": "8000", "x-ratelimit-remaining-tokens": "8000", "x-ratelimit-reset-tokens": "1ms",
    "x-ratelimit-limit-requests": "1000", "x-ratelimit-remaining-requests": "999",
}


def rate_error(*, message="Limit 1000, Requested 1231.", type="tokens", headers=None):
    return httpx.Response(429, json={"error": {"code": "rate_limit_exceeded", "type": type,
        "message": f"Rate limit for private-org and private-key: {message}"}}, headers=headers or FULL_INPUT_HEADERS)


def test_full_combined_headers_do_not_allow_second_request_to_exceed_output_tpm(clock):
    config = settings()
    requests, attempts = [], []

    def handler(request):
        requests.append(clock.now)
        assert json.loads(request.content)["max_completion_tokens"] == 900
        return completion(usage={"prompt_tokens": 100, "completion_tokens": 500, "total_tokens": 600}, headers=FULL_INPUT_HEADERS)

    transport = httpx.MockTransport(handler)
    call(config, transport, on_call=lambda: attempts.append(1))
    call(settings(), transport, remaining_seconds=65, on_call=lambda: attempts.append(1))
    assert requests == [0, pytest.approx(60.01)]
    assert len(attempts) == 2 and clock.waits == [pytest.approx(60.01)]
    guard = ai._guard_for(config.groq_key, config.groq_model)
    assert sum(charge.output_tokens for charge in guard.charges) == 500
    assert sum(charge.tokens for charge in guard.charges) == 100


def test_output_wait_cannot_expire_run_or_count_an_unmade_request(clock):
    requests, attempts = [], []

    def handler(request):
        requests.append(request)
        return completion(usage={"prompt_tokens": 100, "completion_tokens": 500, "total_tokens": 600}, headers=FULL_INPUT_HEADERS)

    config, transport = settings(), httpx.MockTransport(handler)
    call(config, transport, on_call=lambda: attempts.append(1))
    with pytest.raises(ai.AIError, match="time budget") as raised:
        call(config, transport, remaining_seconds=5, on_call=lambda: attempts.append(1))
    assert raised.value.code == "rate_limit" and not raised.value.fatal
    assert raised.value.retry_after >= 60
    assert len(requests) == len(attempts) == 1 and not clock.waits


def test_extraction_and_ai_matching_share_output_window_and_keep_source_facts(clock):
    from app.discovery.ranking import rank_listings
    config = settings(groq_model="qwen/qwen3.8-27b")
    requests, attempts = [], []

    def handler(request):
        payload = json.loads(request.content)
        requests.append(clock.now)
        assert payload["max_completion_tokens"] == 900 and payload["reasoning_effort"] == "none"
        if len(requests) == 1:
            return completion(extraction(0), usage={"prompt_tokens": 1500, "completion_tokens": 500, "total_tokens": 2000}, headers=FULL_INPUT_HEADERS)
        items = json.loads(payload["messages"][1]["content"])["openings"]
        return completion({"verdicts": [{"id": item["id"], "role_fit": "strong", "location_fit": "match", "eligibility_fit": "unknown", "reason": "Software internship"} for item in items]},
            usage={"prompt_tokens": 1000, "completion_tokens": 350, "total_tokens": 1350}, headers=FULL_INPUT_HEADERS)

    prefs, transport = DiscoveryPreferences(roles=["software engineer"]), httpx.MockTransport(handler)
    result = ListingExtractor(config, transport).extract(source(0), prefs, remaining_seconds=130, on_call=lambda: attempts.append(1))
    assert result.listings and result.listings[0].requirements[0].excerpt == "Python is required."
    rows = rank_listings(prefs, result.listings, config, transport, remaining_seconds=130, on_call=lambda: attempts.append(1))
    assert len(rows) == 1 and rows[0].score > 0
    assert rows[0].requirements == result.listings[0].requirements
    assert any("AI fit" in reason for reason in rows[0].reasons)
    assert len(requests) == len(attempts) == 2 and requests[1] >= 60 and len(clock.waits) == 1


def test_exact_completion_usage_allows_two_small_output_calls_in_one_minute(clock):
    config = settings(discovery_ai_max_output_tokens=500)
    requests = []

    def handler(request):
        requests.append(clock.now)
        return completion(usage={"prompt_tokens": 100, "completion_tokens": 500, "total_tokens": 600}, headers=FULL_INPUT_HEADERS)

    transport = httpx.MockTransport(handler)
    for _ in range(3):
        call(config, transport, remaining_seconds=65)
    assert requests[:2] == [0, 0] and requests[2] >= 60
    assert len(clock.waits) == 1


@pytest.mark.parametrize("usage", [None, {"total_tokens": 50}, {"prompt_tokens": 100}, {"prompt_tokens": 100, "completion_tokens": "0"}, {"completion_tokens": True}])
def test_missing_or_malformed_completion_usage_keeps_reserved_output(clock, usage):
    config, transport = settings(), httpx.MockTransport(lambda request: completion(usage=usage))
    call(config, transport)
    guard = ai._guard_for(config.groq_key, config.groq_model)
    assert guard.charges[0].output_tokens == 900
    call(config, transport, remaining_seconds=65)
    assert len(clock.waits) == 1


def test_completion_usage_reconciles_independently_of_missing_prompt_usage(clock):
    config = settings()
    transport = httpx.MockTransport(lambda request: completion(usage={"completion_tokens": 50}))
    call(config, transport)
    guard = ai._guard_for(config.groq_key, config.groq_model)
    assert guard.charges[0].tokens > 0 and guard.charges[0].output_tokens == 50
    call(config, transport)
    assert not clock.waits


def test_input_admission_does_not_add_large_output_reservation_to_input_window(clock):
    config = settings(discovery_ai_tpm=1200)
    payloads = []

    def handler(request):
        payloads.append(json.loads(request.content))
        return completion(usage={"prompt_tokens": 1000, "completion_tokens": 100, "total_tokens": 1100})

    ai.structured_call(config, Output, system="JSON", user="x" * 2400, transport=httpx.MockTransport(handler))
    assert len(payloads) == 1 and payloads[0]["max_completion_tokens"] == 900
    assert not clock.waits


def test_oversized_configured_output_is_rejected_locally_without_silent_shrinking(clock):
    with pytest.raises(ai.AIError) as raised:
        call(settings(discovery_ai_max_output_tokens=1200), httpx.MockTransport(lambda request: pytest.fail("Output request exceeds OTPM")),
            on_call=lambda: pytest.fail("No HTTP attempt"))
    assert raised.value.code == "output_limit" and raised.value.dimension == "output"
    assert raised.value.limit == 1000 and raised.value.requested == 1200 and not raised.value.fatal
    assert not clock.waits


def test_observed_1000_requested_1231_full_header_shape_never_retries_or_alters_prompt_ratio(clock):
    requests, attempts = [], []
    config = settings(groq_model="qwen/qwen3.8-27b")

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        assert body["reasoning_effort"] == "none" and body["max_completion_tokens"] == 900
        return rate_error()

    with pytest.raises(ai.AIError) as raised:
        call(config, httpx.MockTransport(handler), remaining_seconds=65, on_call=lambda: attempts.append(1))
    error = raised.value
    assert error.code == "output_limit" and error.status == 429 and error.dimension == "output"
    assert error.limit == 1000 and error.requested == 1231 and error.retry_after is None
    assert not error.fatal and not ai.ai_warning_is_fatal(str(error))
    assert len(requests) == len(attempts) == 1 and not clock.waits
    guard = ai._guard_for(config.groq_key, config.groq_model)
    assert guard.provider_output_limit == 1000 and guard.provider_limit == 8000
    assert guard.prompt_ratio == 1 / 3 and guard.blocked_until == 0
    assert sum(charge.output_tokens for charge in guard.charges) == 0
    assert "private-org" not in str(error) and "private-key" not in str(error)


def test_explicit_smaller_output_cap_is_learned_without_retry_or_silent_reduction(clock):
    count = 0
    config = settings()

    def handler(request):
        nonlocal count
        count += 1
        return rate_error(message="Output tokens per minute (OTPM): Limit 500, Requested 900.")

    transport = httpx.MockTransport(handler)
    for _ in range(2):
        with pytest.raises(ai.AIError) as raised:
            call(config, transport, remaining_seconds=65)
        assert raised.value.code == "output_limit" and raised.value.limit == 500
    assert count == 1 and not clock.waits
    assert ai._guard_for(config.groq_key, config.groq_model).provider_output_limit == 500
    # A new explicitly configured request fitting the learned cap is allowed.
    assert call(settings(discovery_ai_max_output_tokens=500), httpx.MockTransport(lambda request: completion())).title == "complete"


def test_explicit_input_cap_never_changes_output_cap_or_prompt_ratio(clock):
    config = settings()
    with pytest.raises(ai.AIError) as raised:
        call(config, httpx.MockTransport(lambda request: rate_error(message="Input tokens per minute (ITPM): Limit 1000, Requested 1231.")))
    error = raised.value
    assert error.code == "input_limit" and error.dimension == "input" and error.limit == 1000
    guard = ai._guard_for(config.groq_key, config.groq_model)
    assert guard.provider_limit == 1000 and guard.provider_output_limit is None and guard.prompt_ratio == 1 / 3
    assert not clock.waits


def test_ambiguous_unlabelled_cap_is_not_guessed_as_input_or_output(clock):
    config = settings()
    with pytest.raises(ai.AIError) as raised:
        call(config, httpx.MockTransport(lambda request: rate_error(message="Limit 700, Requested 1231.")))
    assert raised.value.code == "request_size" and raised.value.dimension == "tokens"
    guard = ai._guard_for(config.groq_key, config.groq_model)
    assert guard.provider_limit == 8000 and guard.provider_output_limit is None and guard.prompt_ratio == 1 / 3
    assert not clock.waits


def test_full_generic_1ms_reset_never_authorizes_output_rate_retry(clock):
    config, transport = settings(), httpx.MockTransport(lambda request: rate_error(message="Output tokens per minute: Limit 1000, Requested 900."))
    with pytest.raises(ai.AIError) as raised:
        call(config, transport, remaining_seconds=65)
    assert raised.value.code == "rate_limit" and raised.value.dimension == "output"
    assert raised.value.retry_after is None and not clock.waits
    # A NEW request waits the conservative output window, not 1ms.
    assert call(config, httpx.MockTransport(lambda request: completion()), remaining_seconds=65).title == "complete"
    assert clock.waits == [pytest.approx(60.01)]


def test_output_rate_retry_after_is_used_once_when_request_itself_fits(clock):
    count, attempts = 0, []

    def handler(request):
        nonlocal count
        count += 1
        return rate_error(message="Output tokens per minute: Limit 1000, Requested 900.", headers={**FULL_INPUT_HEADERS, "retry-after": "1"}) if count == 1 else completion()

    assert call(settings(), httpx.MockTransport(handler), remaining_seconds=5, on_call=lambda: attempts.append(1)).title == "complete"
    assert count == len(attempts) == 2 and len(clock.waits) == 1


def test_oversized_body_request_cannot_be_fixed_by_retry_after_header(clock):
    attempts = []
    with pytest.raises(ai.AIError) as raised:
        call(settings(), httpx.MockTransport(lambda request: rate_error(headers={**FULL_INPUT_HEADERS, "retry-after": "1"})),
            remaining_seconds=65, on_call=lambda: attempts.append(1))
    assert raised.value.code == "output_limit" and raised.value.retry_after is None
    assert len(attempts) == 1 and not clock.waits


@pytest.mark.parametrize("body", [
    {"error": {"code": "different_code", "type": "tokens", "message": "Limit 500, Requested 900."}},
    {"error": {"code": "rate_limit_exceeded", "type": "requests", "message": "Limit 500, Requested 900."}},
    {"error": {"code": "rate_limit_exceeded", "type": "tokens", "message": "Limit 500, Requested 900. Limit 600."}},
    {"error": {"code": "rate_limit_exceeded", "type": "tokens", "message": "Output and input tokens: Limit 500, Requested 900."}},
    {"error": {"code": "rate_limit_exceeded", "type": "tokens", "message": "Limit NaN, Requested 900."}},
    {"error": {"code": "rate_limit_exceeded", "type": "tokens", "message": "Limit 1,000, Requested 900."}},
    {"error": {"code": "rate_limit_exceeded", "type": "tokens", "message": "Limit 500.5, Requested 900."}},
    {"error": {"code": "rate_limit_exceeded", "type": "tokens", "message": "Limit 500, Requested NaN."}},
    {"error": {"code": "rate_limit_exceeded", "type": "tokens", "message": "private" * 2000}},
])
def test_untrusted_or_oversized_error_body_never_changes_numeric_caps(clock, body):
    config = settings()
    with pytest.raises(ai.AIError) as raised:
        call(config, httpx.MockTransport(lambda request: httpx.Response(429, json=body, headers=FULL_INPUT_HEADERS)))
    assert raised.value.code == "rate_limit" and raised.value.dimension is None and raised.value.limit is None
    assert ai._guard_for(config.groq_key, config.groq_model).provider_output_limit is None
    assert "private" not in str(raised.value) and not clock.waits


@pytest.mark.parametrize("model", ["qwen/qwen3.8-27b", "qwen/other", "other/provider-model"])
def test_reasoning_is_disabled_only_for_existing_discovery_qwen_model(clock, model):
    payloads = []

    def handler(request):
        payloads.append(json.loads(request.content))
        return completion()

    call(settings(groq_model=model), httpx.MockTransport(handler))
    assert payloads[0]["model"] == model and payloads[0]["max_completion_tokens"] == 900
    if model == "qwen/qwen3.8-27b":
        assert payloads[0]["reasoning_effort"] == "none"
    else:
        assert "reasoning_effort" not in payloads[0]


def test_incomplete_response_reconciles_actual_output_without_accepting_partial_json(clock):
    config = settings()
    with pytest.raises(ai.AIError) as raised:
        call(config, httpx.MockTransport(lambda request: completion(finish="length", usage={"prompt_tokens": 100, "completion_tokens": 900, "total_tokens": 1000})))
    assert raised.value.code == "incomplete" and not raised.value.fatal
    guard = ai._guard_for(config.groq_key, config.groq_model)
    assert guard.charges[0].tokens == 100 and guard.charges[0].output_tokens == 900


def test_slow_response_keeps_output_window_from_actual_completion(clock):
    config = settings()

    def slow(request):
        clock.now = 20
        return completion(usage={"prompt_tokens": 100, "completion_tokens": 500, "total_tokens": 600})

    call(config, httpx.MockTransport(slow))
    clock.now = 61
    call(config, httpx.MockTransport(lambda request: completion()), remaining_seconds=65)
    assert clock.now >= 80 and clock.waits == [pytest.approx(19.01)]
