from __future__ import annotations

import hashlib
import json
from datetime import datetime

import httpx
import pytest

from app.config import Settings
from app.discovery.contracts import SearchTask
from app.discovery.provider import DiscoveryWebClient, ProviderError
from app.sources import FETCH_ENDPOINT, MAX_CONTENT_CHARS, SEARCH_ENDPOINT


KEY = "test-key-not-a-real-credential"
PUBLIC = "https://careers.example.org/jobs"


def client(handler):
    return DiscoveryWebClient(Settings(tinyfish_key=KEY), httpx.MockTransport(handler))


def task(**updates):
    return SearchTask(intent="company", query="Example internship", purpose="Find public openings",
                      label="Example", company="Example", **updates)


def test_search_rest_fields_domain_policy_and_public_leads():
    def handler(request):
        assert str(request.url).startswith(SEARCH_ENDPOINT)
        assert request.method == "GET"
        assert request.headers["X-API-Key"] == KEY
        assert request.url.params["query"] == "Example internship"
        assert request.url.params["purpose"] == "Find public openings"
        assert request.url.params["include_domains"] == "example.org,ashbyhq.com"
        assert request.url.params["exclude_domains"] == "blocked.example.org"
        return httpx.Response(200, json={"results": [
            {"url": PUBLIC + "#top", "title": "Intern"},
            {"url": PUBLIC, "title": "Duplicate"},
            {"url": "https://blocked.example.org/job"},
            {"url": "https://example.org.evil.com/job"},
            {"url": "https://user:secret@example.org/job"},
            {"url": "https://example.org/login"},
            {"url": "http://127.0.0.1/job"},
            {"url": ["malformed"]}, None,
        ]})
    lead, = client(handler).search(task(include_domains=("example.org", "ashbyhq.com"),
                                      exclude_domains=("blocked.example.org",)))
    assert lead.url == PUBLIC and lead.title == "Intern"
    assert lead.organization == "Example" and lead.via == "search"
    assert lead.source_url == PUBLIC


def test_fetch_retains_links_iframes_requested_identity_and_snapshot_hash():
    original = PUBLIC + "#jobs"
    final = "https://jobs.example.org/team/"
    text = "# Internships\nExact original page text.\n"

    def handler(request):
        assert str(request.url).rstrip("/") == FETCH_ENDPOINT
        assert request.method == "POST"
        body = json.loads(request.content)
        assert body == {"urls": [PUBLIC], "format": "markdown", "links": True, "image_links": False,
                        "iframe_links": True, "ttl": 3600, "per_url_timeout_ms": 25_000}
        return httpx.Response(200, json={"results": [{
            "url": PUBLIC, "final_url": final, "text": text, "title": "Jobs",
            "links": ["../opening/1#apply", "https://jobs.example.org/opening/1", "javascript:alert(1)",
                      "http://localhost/job", "https://jobs.example.org/login", "https://jobs.example.org/job?token=secret",
                      "http://[invalid-ip/", "https://jobs.example.org/%6cogin", "https://jobs.example.org/job?%74oken=secret"],
            "iframe_links": ["https://jobs.ashbyhq.com/example", "http://169.254.169.254/"],
        }], "errors": []})
    pages, errors = client(handler).fetch([original], ttl=3600)
    assert not errors
    page, = pages
    assert page.requested_url == original and page.snapshot.url == final
    assert page.snapshot.text == text and page.snapshot.mode == "live"
    assert page.snapshot.content_hash == hashlib.sha256(text.encode()).hexdigest()
    assert page.snapshot.id == "source-" + hashlib.sha256(final.encode()).hexdigest()[:16]
    assert datetime.fromisoformat(page.snapshot.checked_at).tzinfo is not None
    assert page.links == ["https://jobs.example.org/opening/1", "https://jobs.ashbyhq.com/example"]


@pytest.mark.parametrize("format,raw", [
    ("json", {"jobs": [{"title": "Intern", "url": PUBLIC + "/1"}]}),
    ("json", [{"title": "Intern"}]),
    ("json", '{ "jobs": [] }'),
    ("markdown", '[{"title":"Intern"}]'),
])
def test_public_feed_json_body_is_preserved_and_hashes_are_deterministic(format, raw):
    def handler(request):
        assert json.loads(request.content)["format"] == format
        return httpx.Response(200, json={"results": [{"url": PUBLIC, "text": raw}]})
    page, = client(handler).fetch([PUBLIC], format=format)[0]
    assert page.json_body == (json.loads(raw) if isinstance(raw, str) else raw)
    assert page.snapshot.text == (raw if isinstance(raw, str) else json.dumps(
        raw, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    assert page.snapshot.content_hash == hashlib.sha256(page.snapshot.text.encode()).hexdigest()


def test_fetch_retains_earlier_json_body_field():
    page, = client(lambda _: httpx.Response(200, json={"results": [{
        "url": PUBLIC, "text": "", "json": {"jobs": []},
    }]})).fetch([PUBLIC], format="json")[0]
    assert page.json_body == {"jobs": []}


def test_snapshot_identity_stays_stable_but_version_hash_changes_with_content():
    responses = iter(["First opening", "Updated opening"])
    c = client(lambda _: httpx.Response(200, json={"results": [{"url": PUBLIC, "text": next(responses)}]}))
    first, second = c.fetch([PUBLIC])[0][0], c.fetch([PUBLIC])[0][0]
    assert first.snapshot.id == second.snapshot.id
    assert first.snapshot.content_hash != second.snapshot.content_hash


def test_fetch_per_url_failures_unsafe_redirect_and_missing_do_not_discard_successes():
    bot, redirect, missing = (PUBLIC + f"/{name}" for name in ("bot", "redirect", "missing"))
    secret_url = "https://user:private@private.example.org/login"
    def handler(request):
        assert secret_url not in json.loads(request.content)["urls"]
        return httpx.Response(200, json={"results": [
            {"url": PUBLIC, "text": "Open internship"},
            {"url": redirect, "final_url": "http://10.0.0.1/secret", "text": "PRIVATE"},
            {"url": "https://unsolicited.example.org/", "text": "Ignored"},
        ], "errors": [{"url": bot, "error": "bot_blocked", "message": KEY}]})
    pages, errors = client(handler).fetch([PUBLIC, bot, redirect, missing, secret_url])
    assert [p.requested_url for p in pages] == [PUBLIC]
    assert set(errors) == {bot, redirect, missing, secret_url}
    assert "bot_blocked" in errors[bot]
    assert all(KEY not in error and "PRIVATE" not in error for error in errors.values())


@pytest.mark.parametrize("text", ["Please sign in to view openings", "Login required to access this page",
                                 "Access denied", "Verify you are human", "Complete the CAPTCHA"])
def test_protected_content_is_not_a_snapshot(text):
    pages, errors = client(lambda _: httpx.Response(200, json={"results": [{"url": PUBLIC, "text": text}]})).fetch([PUBLIC])
    assert not pages and "wall" in errors[PUBLIC]


@pytest.mark.parametrize("text,format", [("", "markdown"), ("x" * (MAX_CONTENT_CHARS + 1), "markdown"),
                                        ("not JSON", "json")])
def test_unusable_content_is_per_url_failure(text, format):
    pages, errors = client(lambda _: httpx.Response(200, json={"results": [{"url": PUBLIC, "text": text}]})).fetch([PUBLIC], format=format)
    assert not pages and PUBLIC in errors


def test_explicit_failure_wins_over_conflicting_success():
    pages, errors = client(lambda _: httpx.Response(200, json={
        "results": [{"url": PUBLIC, "text": "Contradictory success"}],
        "errors": [{"url": PUBLIC, "error": KEY, "message": KEY}],
    })).fetch([PUBLIC])
    assert not pages and errors[PUBLIC] == "Public source fetch failed (source_failure)."


@pytest.mark.parametrize("status", [301, 400, 401, 402, 403, 404, 422, 429, 500, 503])
def test_http_errors_are_sanitized_and_never_retried(status):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, headers={"location": "http://localhost/"}, json={"error": KEY})
    with pytest.raises(ProviderError) as raised:
        client(handler).fetch([PUBLIC])
    assert len(calls) == 1 and KEY not in str(raised.value)
    assert raised.value.status == f"HTTP_{status}"


@pytest.mark.parametrize("error", [httpx.ReadTimeout, httpx.ConnectError])
def test_http_network_errors_are_sanitized(error):
    def handler(request):
        raise error(KEY, request=request)
    with pytest.raises(ProviderError) as raised:
        client(handler).search(task())
    assert KEY not in str(raised.value)


@pytest.mark.parametrize("payload", [[], {"results": None}, {"results": [], "errors": {}}])
def test_invalid_fetch_envelope(payload):
    with pytest.raises(ProviderError):
        client(lambda _: httpx.Response(200, json=payload)).fetch([PUBLIC])


def test_no_key_invalid_urls_and_empty_input_never_make_a_request():
    def forbidden(_):
        pytest.fail("Unexpected provider call")
    c = client(forbidden)
    assert c.fetch([]) == ([], {})
    assert c.fetch(["http://127.0.0.1/"])[0] == []
    with pytest.raises(ProviderError):
        DiscoveryWebClient(Settings(tinyfish_key=""), httpx.MockTransport(forbidden)).search(task())
    with pytest.raises(ProviderError):
        c.fetch([PUBLIC] * 11)
    with pytest.raises(ProviderError):
        c.fetch([PUBLIC], ttl=True)
    with pytest.raises(ProviderError):
        c.fetch([PUBLIC], format="xml")


def test_malformed_json_is_sanitized():
    with pytest.raises(ProviderError, match="invalid JSON"):
        client(lambda _: httpx.Response(200, text="not JSON " + KEY)).fetch([PUBLIC])


def test_size_limit_applies_to_whole_provider_response(monkeypatch):
    monkeypatch.setattr("app.discovery.provider.MAX_RESPONSE_BYTES", 100)
    with pytest.raises(ProviderError, match="bounded size"):
        client(lambda _: httpx.Response(200, json={"results": [{"url": PUBLIC, "text": "x" * 200}]})).fetch([PUBLIC])


@pytest.mark.parametrize("url", [
    "https://example.org/profile/person", "https://example.org/profiles/person",
    "https://example.org/candidates/person", "https://example.org/careers?email=person%40example.org",
    "https://example.org/careers?name=Person", "https://example.org/careers#email=person%40example.org",
    "https://example.org/careers?redirect_url=https%3A%2F%2Fexample.org%2Flogin",
])
def test_shared_url_validation_rejects_profile_and_personal_sources_without_request(url):
    pages, errors = client(lambda _: pytest.fail("Private source must not be fetched")).fetch([url])
    assert not pages and errors == {url: "Source URL is not an allowed public source."}


@pytest.mark.parametrize("url", [
    "http://www.example.org/careers/?department=Engineering&employmentType=Intern&jobId=abc123",
    "https://jobs.ashbyhq.com/example?team=Engineering&employmentType=Intern",
    "https://api.lever.co/v0/postings/example?mode=json",
    "https://api.smartrecruiters.com/v1/companies/example/postings?limit=50",
])
def test_canonical_validation_does_not_rewrite_request_or_final_url_parameters(url):
    def handler(request):
        assert json.loads(request.content)["urls"] == [url]
        return httpx.Response(200, json={"results": [{"url": url, "final_url": url, "text": "Open internship"}]})
    pages, errors = client(handler).fetch([url])
    assert not errors
    assert pages[0].requested_url == url and pages[0].snapshot.url == url


def test_search_and_page_links_use_the_same_private_url_policy():
    private = "https://careers.example.org/profile/person"
    personal = "https://careers.example.org/jobs?email=person%40example.org"
    c = client(lambda _: httpx.Response(200, json={"results": [{"url": private}, {"url": personal}, {"url": PUBLIC}]}))
    assert [lead.url for lead in c.search(task())] == [PUBLIC]
    pages, errors = client(lambda _: httpx.Response(200, json={"results": [{
        "url": PUBLIC, "text": "Open internship", "links": [private, personal, PUBLIC + "/123"],
    }]})).fetch([PUBLIC])
    assert not errors and pages[0].links == [PUBLIC + "/123"]


def test_redirect_to_profile_page_is_rejected_even_if_response_has_readable_text():
    pages, errors = client(lambda _: httpx.Response(200, json={"results": [{
        "url": PUBLIC, "final_url": "https://example.org/profiles/person", "text": "Private profile data",
    }]})).fetch([PUBLIC])
    assert not pages and "unsafe redirect" in errors[PUBLIC]
