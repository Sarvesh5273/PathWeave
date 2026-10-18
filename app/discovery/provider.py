"""Injectable public Search/Fetch transport; orchestration owns budgets and caches.

REST contracts: https://docs.tinyfish.ai/search-api/reference and
https://docs.tinyfish.ai/fetch-api/reference (checked October 16, 2026).
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from app.discovery.contracts import SearchTask, SourceLead, WebPage
from app.discovery.urls import canonical_url
from app.models import SourceSnapshot, utc_now
from app.sources import FETCH_ENDPOINT, MAX_CONTENT_CHARS, SEARCH_ENDPOINT, TinyFishError, _public_url


MAX_RESPONSE_BYTES = 4_000_000
FETCH_ERROR_CODES = frozenset({
    "target_http_error", "page_not_found", "target_unreachable", "timeout", "bot_blocked",
    "empty_content", "login_required", "content_too_large", "invalid_url", "invalid_redirect_url",
    "proxy_error", "conditional_unsupported", "selector_not_matched", "selector_unsupported",
})


class ProviderError(RuntimeError):
    """Safe display text, never a provider body, with optional run recovery metadata.

    ``recoverable`` means status can be checked, not permission to resubmit a run.
    ``status`` is an Agent state, local failure label, or ``HTTP_<code>``.
    """

    def __init__(self, message: str, *, run_id: str | None = None,
                 status: str | None = None, recoverable: bool = False) -> None:
        super().__init__(message)
        self.run_id = _run_id(run_id)
        self.status = status
        self.recoverable = recoverable


def _run_id(value: Any) -> str | None:
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value) else None


def _safe_url(value: Any) -> str | None:
    try:
        # Use the shared, stricter private/profile/personal URL policy solely to
        # validate. Its canonical identity strips filters and must NOT replace
        # the request URL (Ashby employmentType, ATS feed query parameters, etc.).
        if not isinstance(value, str) or canonical_url(value) is None:
            return None
        return _public_url(value)
    except (TinyFishError, ValueError, UnicodeError):
        return None


def _safe_link(base: str, value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return _safe_url(urljoin(base, value))
    except ValueError:
        return None


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _client(settings: Any, transport: httpx.BaseTransport | None, *,
            timeout: httpx.Timeout | None = None, accept: str = "application/json") -> httpx.Client:
    key = getattr(settings, "tinyfish_key", "")
    if not key:
        raise ProviderError("TinyFish API key is not configured on the server.", status="NOT_CONFIGURED")
    return httpx.Client(
        headers={"X-API-Key": key, "Accept": accept},
        timeout=timeout or httpx.Timeout(40.0, connect=8.0, read=35.0, write=8.0, pool=3.0),
        follow_redirects=False, transport=transport,
    )


def _http_error(code: int, *, run_id: str | None = None) -> ProviderError:
    messages = {
        400: "TinyFish rejected the request.",
        401: "TinyFish authentication failed; check the server API key.",
        402: "TinyFish allowance or credits are exhausted; review the provider account or wait for reset.",
        403: "TinyFish denied access to this request.",
        404: "TinyFish endpoint or run is unavailable.",
        422: "TinyFish rejected the extraction options.",
        429: "TinyFish rate limit reached; check an existing run before retrying.",
    }
    return ProviderError(messages.get(code, "TinyFish provider returned an error."),
                         status=f"HTTP_{code}", run_id=run_id, recoverable=bool(run_id))


def _read_json(response: httpx.Response) -> dict[str, Any]:
    body = bytearray()
    for chunk in response.iter_bytes():
        body.extend(chunk)
        if len(body) > MAX_RESPONSE_BYTES:
            raise ProviderError("TinyFish response exceeded the bounded size limit.", status="CONTENT_TOO_LARGE")
    try:
        data = json.loads(body)
    except (ValueError, UnicodeError, RecursionError):
        raise ProviderError("TinyFish returned an invalid JSON response.", status="INVALID_RESPONSE") from None
    if not isinstance(data, dict):
        raise ProviderError("TinyFish returned an unexpected response shape.", status="INVALID_RESPONSE")
    return data


def _request_json(settings: Any, transport: httpx.BaseTransport | None,
                  method: str, url: str, *, timeout: httpx.Timeout | None = None, **kwargs: Any) -> dict[str, Any]:
    try:
        with _client(settings, transport, timeout=timeout) as client:
            with client.stream(method, url, **kwargs) as response:
                if not 200 <= response.status_code < 300:
                    raise _http_error(response.status_code)
                return _read_json(response)
    except httpx.TimeoutException:
        raise ProviderError("TinyFish request timed out; no automatic retry was made.", status="TIMEOUT") from None
    except httpx.RequestError:
        raise ProviderError("TinyFish could not be reached; no automatic retry was made.", status="NETWORK_ERROR") from None


def _blocked_content(text: str) -> bool:
    # Specific account/challenge language, not ordinary job-description mentions of security.
    return bool(re.search(
        r"(?:sign in|log in|login) (?:is )?required to (?:view|access)|"
        r"please (?:sign in|log in) to (?:view|access)|"
        r"you (?:must|need to) (?:sign in|log in) to (?:view|access)|"
        r"\b(?:access denied|verify (?:that )?you are (?:a )?human|"
        r"complete (?:the |a )?captcha|captcha challenge|paywall|subscription required)\b",
        text, re.I,
    ))


def _domain_matches(url: str, domain: str) -> bool:
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    domain = domain.lower().rstrip(".")
    return host == domain or host.endswith("." + domain)


class DiscoveryWebClient:
    def __init__(self, settings: Any, transport: httpx.BaseTransport | None = None) -> None:
        self.settings = settings
        self.transport = transport

    def search(self, task: SearchTask) -> list[SourceLead]:
        if not task.query.strip() or len(task.query) > 2000 or len(task.purpose) > 2000:
            raise ProviderError("Search query and purpose must fit the provider's 2000-character limit.")
        params = {"query": task.query, "language": "en"}
        if task.purpose.strip():
            params["purpose"] = task.purpose
        if task.include_domains:
            params["include_domains"] = ",".join(task.include_domains)
        if task.exclude_domains:
            params["exclude_domains"] = ",".join(task.exclude_domains)
        data = _request_json(self.settings, self.transport, "GET", SEARCH_ENDPOINT, params=params,
                             timeout=httpx.Timeout(15.0, connect=8.0, pool=3.0))
        if not isinstance(data.get("results"), list):
            raise ProviderError("TinyFish search response has no result list.", status="INVALID_RESPONSE")
        leads: list[SourceLead] = []
        seen: set[str] = set()
        for row in data["results"]:
            if not isinstance(row, dict) or not (url := _safe_url(row.get("url"))):
                continue
            if url in seen or any(_domain_matches(url, d) for d in task.exclude_domains):
                continue
            if task.include_domains and not any(_domain_matches(url, d) for d in task.include_domains):
                continue
            seen.add(url)
            leads.append(SourceLead(url=url, title=row.get("title") if isinstance(row.get("title"), str) else "",
                                    organization=task.company, via="search", source_url=url, intent=task.intent,
                                    snippet=(row.get("snippet") or row.get("description"))[:1000] if isinstance(row.get("snippet") or row.get("description"),str) else None))
        return leads

    def fetch(self, urls: list[str], format: str = "markdown", ttl: int = 0) -> tuple[list[WebPage], dict[str, str]]:
        if not isinstance(urls, list) or len(urls) > 10 or any(not isinstance(url, str) for url in urls):
            raise ProviderError("Fetch needs at most 10 public source URLs.")
        if format not in {"markdown", "html", "json"}:
            raise ProviderError("Fetch format must be markdown, html or json.")
        if isinstance(ttl, bool) or not isinstance(ttl, int) or not 0 <= ttl <= 9_007_199_254_740_991:
            raise ProviderError("Fetch cache tolerance must be a nonnegative safe integer.")
        errors: dict[str, str] = {}
        requests: dict[str, list[str]] = {}
        for original in dict.fromkeys(urls):
            if url := _safe_url(original):
                requests.setdefault(url, []).append(original)
            else:
                errors[original] = "Source URL is not an allowed public source."
        if not requests:
            return [], errors
        data = _request_json(self.settings, self.transport, "POST", FETCH_ENDPOINT, json={
            "urls": list(requests), "format": format, "links": True, "image_links": False,
            "iframe_links": True, "ttl": ttl, "per_url_timeout_ms": 25_000,
        })
        if not isinstance(data.get("results"), list) or not isinstance(data.get("errors", []), list):
            raise ProviderError("TinyFish fetch returned an unexpected response shape.", status="INVALID_RESPONSE")
        pages_by_url: dict[str, WebPage] = {}
        failures: dict[str, str] = {}
        checked_at = utc_now()
        for row in data["results"]:
            if not isinstance(row, dict) or not isinstance(row.get("url"), str) or row["url"] not in requests:
                continue  # Never ingest an unsolicited page.
            requested = row["url"]
            final = _safe_url(row.get("final_url") or requested)
            if not final:
                failures[requested] = "Public fetch rejected a protected or unsafe redirect."
                continue
            raw = row.get("text")
            json_body = row.get("json") if isinstance(row.get("json"), (dict, list)) else None
            try:
                if isinstance(raw, (dict, list)):
                    json_body = raw
                    text = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
                elif isinstance(raw, str):
                    text = raw
                    if not raw.strip() and json_body is not None:
                        text = json.dumps(json_body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
                    if raw.lstrip().startswith(("{", "[")):
                        try:
                            parsed = json.loads(raw)
                            if isinstance(parsed, (dict, list)):
                                json_body = parsed
                        except (ValueError, RecursionError):
                            pass
                elif json_body is not None:
                    text = json.dumps(json_body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
                else:
                    text = ""
            except (ValueError, TypeError, RecursionError):
                failures[requested] = "Public fetch returned malformed JSON content."
                continue
            if not text.strip():
                failures[requested] = "Public fetch returned no readable content."
            elif len(text) > MAX_CONTENT_CHARS:
                failures[requested] = "Public source exceeds the bounded extraction size limit."
            elif _blocked_content(text):
                failures[requested] = "Public fetch encountered a login, access or bot-protection wall."
            elif format == "json" and json_body is None:
                failures[requested] = "Public fetch returned malformed JSON content."
            else:
                links: list[str] = []
                for field in ("links", "iframe_links"):
                    for link in row.get(field, []) if isinstance(row.get(field), list) else []:
                        if (safe := _safe_link(final, link)) and safe not in links:
                            links.append(safe)
                pages_by_url[requested] = WebPage(
                    snapshot=SourceSnapshot(id="source-" + _hash(final)[:16], url=final,
                                            title=row.get("title") if isinstance(row.get("title"), str) else "",
                                            text=text, checked_at=checked_at, content_hash=_hash(text), mode="live"),
                    requested_url=requested, links=links, json_body=json_body,
                )
        for row in data.get("errors", []):
            if not isinstance(row, dict) or not isinstance(row.get("url"), str) or row["url"] not in requests:
                continue
            code = row.get("error")
            code = code if isinstance(code, str) and code in FETCH_ERROR_CODES else "source_failure"
            failures[row["url"]] = f"Public source fetch failed ({code})."
        pages: list[WebPage] = []
        for requested, originals in requests.items():
            if requested in failures or requested not in pages_by_url:
                for original in originals:
                    errors[original] = failures.get(requested, "TinyFish returned no result for this source.")
            else:
                for original in originals:
                    pages.append(pages_by_url[requested].model_copy(update={"requested_url": original}))
        return pages, errors
