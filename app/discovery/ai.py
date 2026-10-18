"""Bounded Groq JSON boundary with process-shared token admission.

One reset wait (and, only with safe reset headers, one 429 re-attempt) is
allowed. No SDK, alternate provider, unsanitized diagnostics or blind retries.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from threading import Lock
from time import monotonic, sleep
from typing import Any, Callable, TypeVar
from urllib.parse import parse_qsl, urljoin, urlsplit, urlunsplit

import httpx
from pydantic import BaseModel, ValidationError


GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
MAX_INPUT_CHARS = 65_000
MAX_RESPONSE_BYTES = 180_000
MAX_ERROR_BYTES = 8192
DEFAULT_TPM = 8000
DEFAULT_OUTPUT_TPM = 1000
DEFAULT_MAX_OUTPUT = 900
Model = TypeVar("Model", bound=BaseModel)


class AIError(RuntimeError):
    """A public-safe warning: provider bodies and credentials are never echoed."""

    def __init__(self, message: str, *, code: str = "invalid_response", status: int | None = None, retry_after: float | None = None,
                 dimension: str | None = None, limit: int | None = None, requested: int | None = None) -> None:
        self.code = code
        self.status = status
        self.retry_after = retry_after
        # Only our whitelisted dimensions/numeric limits, never raw error text.
        self.dimension = dimension
        self.limit = limit
        self.requested = requested
        self.fatal = code in {"configuration", "authentication", "denied", "quota", "request"}
        super().__init__(f"{message} [AI:{code}]")


def ai_warning_is_fatal(message: str) -> bool:
    """Engine integration: malformed/timeout/rate/incomplete != permanent stop."""
    return bool(re.search(r"\[AI:(?:configuration|authentication|denied|quota|request)\]", message))


def _integer_setting(settings: Any, name: str, default: int, minimum: int, maximum: int) -> int:
    value = getattr(settings, name, default)
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise AIError(f"Groq {name} configuration is invalid; no request was made.", code="configuration")
    return value


def _compact_schema(value: Any) -> Any:
    # Shape/enums/required fields and constraints survive. Pydantic remains the
    # authority locally; documentation/default metadata costs prompt tokens only.
    if isinstance(value, dict):
        return {key: ({name: _compact_schema(schema) for name, schema in item.items()} if key in {"properties", "$defs", "definitions"} else _compact_schema(item))
                for key, item in value.items() if key not in {"title", "description", "default", "examples", "$comment"}}
    if isinstance(value, list):
        return [_compact_schema(item) for item in value]
    return value


def _duration(value: str | None) -> float | None:
    """Groq durations (e.g. 1m2.5s), not arbitrary error-body strings."""
    if not value or len(value) > 80:
        return None
    value = value.strip().lower()
    if re.fullmatch(r"\d+(?:\.\d+)?", value):
        seconds = float(value)
    else:
        parts = re.findall(r"(\d+(?:\.\d+)?)(ms|s|m|h|d)", value)
        if not parts or "".join(number + unit for number, unit in parts) != value:
            return None
        seconds = sum(float(number) * {"ms": .001, "s": 1, "m": 60, "h": 3600, "d": 86400}[unit] for number, unit in parts)
    return seconds if math.isfinite(seconds) and 0 <= seconds <= 86400 else None


def _retry_after(headers: httpx.Headers) -> float | None:
    raw = headers.get("retry-after")
    seconds = _duration(raw)
    if seconds is not None:
        return seconds
    if raw and len(raw) <= 80:
        try:
            instant = parsedate_to_datetime(raw)
            if instant.tzinfo is not None:
                seconds = (instant - datetime.now(timezone.utc)).total_seconds()
                return max(0.0, seconds) if math.isfinite(seconds) and seconds <= 86400 else None
        except (ValueError, TypeError, OverflowError):
            pass
    return None


def _header_int(headers: httpx.Headers, name: str) -> int | None:
    value = headers.get(name, "")
    return int(value) if re.fullmatch(r"\d{1,12}", value) else None


@dataclass(frozen=True)
class _RateDetails:
    dimension: str
    limit: int
    requested: int | None = None


def _request_failure_code(response: httpx.Response, deadline: float | None) -> str | None:
    """Expose only known provider codes, never generated source text or keys."""
    if response.status_code != 400:return None
    try:
        chunks=[];size=0
        for chunk in response.iter_bytes():
            remaining_budget(deadline);size+=len(chunk)
            if size>MAX_ERROR_BYTES:return None
            chunks.append(chunk)
        envelope=json.loads(b''.join(chunks))
        code=envelope.get('error',{}).get('code')
        return code if code in {'json_validate_failed','model_not_found','model_decommissioned','context_length_exceeded','invalid_api_key','invalid_request_error'} else None
    except (ValueError,TypeError,AttributeError):return None


def _rate_details(response: httpx.Response, deadline: float | None, *, output_tpm: int) -> _RateDetails | None:
    """Read a small 429 envelope; retain only whitelisted numeric rate metadata.

    A full generic token header is not an output reset. Unknown dimensions stay
    unknown, rather than changing prompt estimates or waiting on that header.
    """
    if response.status_code != 429:
        return None
    try:
        chunks: list[bytes] = []
        size = 0
        for chunk in response.iter_bytes():
            remaining_budget(deadline)
            size += len(chunk)
            if size > MAX_ERROR_BYTES:
                return None
            chunks.append(chunk)
        envelope = json.loads(b"".join(chunks), object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
        error = envelope.get("error") if isinstance(envelope, dict) else None
        if not isinstance(error, dict) or error.get("code") != "rate_limit_exceeded" or error.get("type") not in {"tokens", "input_tokens", "output_tokens"}:
            return None
        message = error.get("message")
        if not isinstance(message, str) or len(message) > MAX_ERROR_BYTES:
            return None
        limits = re.findall(r"\bLimit\s*[:=]?\s*([1-9]\d{0,7})(?!\d|[.,]\d)\b", message, re.I)
        requests = re.findall(r"\bRequested\s*[:=]?\s*(\d{1,8})(?!\d|[.,]\d)\b", message, re.I)
        if re.search(r"\bRequested\b", message, re.I) and not requests:
            return None
        if len(limits) != 1 or len(requests) > 1:
            return None
        limit = int(limits[0])
        requested = int(requests[0]) if requests else None
        explicit_output = error["type"] == "output_tokens" or bool(re.search(r"\b(?:output(?: and input)? tokens?|completion tokens?|OTPM)\b", message, re.I))
        explicit_input = error["type"] == "input_tokens" or bool(re.search(r"\b(?:input(?: and output)? tokens?|prompt tokens?|ITPM)\b", message, re.I))
        if explicit_output and explicit_input:
            return None
        dimension = "output" if explicit_output else "input" if explicit_input else "tokens"
        header_limit = _header_int(response.headers, "x-ratelimit-limit-tokens")
        header_remaining = _header_int(response.headers, "x-ratelimit-remaining-tokens")
        # Observed account shape: generic input header is completely full at
        # 8000 while the numeric limit matches our separately configured 1000
        # output ceiling. Match this known cap only; NEVER assume any smaller
        # unlabelled token limit is output or alter the prompt ratio from it.
        if dimension == "tokens" and limit == output_tpm and header_limit is not None and header_limit > limit and header_remaining == header_limit:
            dimension = "output"
        return _RateDetails(dimension, limit, requested)
    except (ValueError, TypeError, KeyError, UnicodeError):
        return None


@dataclass
class _Charge:
    at: float
    tokens: int
    output_tokens: int = 0


@dataclass
class _TokenGuard:
    # A single slot per credential/model avoids racing provider remaining-token
    # snapshots. This is shared by extractors and matchers in this process ONLY.
    lock: Any = field(default_factory=Lock)
    charges: list[_Charge] = field(default_factory=list)
    provider_limit: int | None = None
    provider_remaining: int | None = None
    provider_output_limit: int | None = None
    provider_output_remaining: int | None = None
    tokens_reset: float = 0.0
    output_reset: float = 0.0
    requests_reset: float = 0.0
    blocked_until: float = 0.0
    prompt_ratio: float = 1 / 3

    def delay(self, tokens: int, tpm: int, output_tokens: int, output_tpm: int) -> float:
        now = monotonic()
        self.charges = [charge for charge in self.charges if charge.at + 60 > now]
        limit = min(tpm, self.provider_limit or tpm)
        if tokens > limit:
            raise AIError("Groq request exceeds the input token-per-minute admission limit; source budget must be reduced explicitly.", code="input_limit", dimension="input", limit=limit, requested=tokens)
        output_limit = min(output_tpm, self.provider_output_limit or output_tpm)
        if output_tokens > output_limit:
            raise AIError("Groq output request exceeds the output token-per-minute admission limit; output budget must be reduced explicitly.", code="output_limit", dimension="output", limit=output_limit, requested=output_tokens)
        delay = max(0.0, self.blocked_until - now, self.requests_reset - now)
        if self.tokens_reset <= now:
            self.provider_remaining = None
        if self.provider_remaining is not None and tokens > self.provider_remaining:
            delay = max(delay, self.tokens_reset - now)
        if self.output_reset <= now:
            self.provider_output_remaining = None
        if self.provider_output_remaining is not None and output_tokens > self.provider_output_remaining:
            delay = max(delay, self.output_reset - now)
        used = sum(charge.tokens for charge in self.charges)
        for charge in self.charges:
            if used + tokens <= limit:
                break
            used -= charge.tokens
            delay = max(delay, charge.at + 60 - now)
        used_output = sum(charge.output_tokens for charge in self.charges)
        for charge in self.charges:
            if used_output + output_tokens <= output_limit:
                break
            used_output -= charge.output_tokens
            delay = max(delay, charge.at + 60 - now)
        return delay

    def headers(self, headers: httpx.Headers, status: int) -> float | None:
        now = monotonic()
        limit = _header_int(headers, "x-ratelimit-limit-tokens")
        if limit is not None and limit > 0:
            self.provider_limit = limit
        remaining = _header_int(headers, "x-ratelimit-remaining-tokens")
        reset = _duration(headers.get("x-ratelimit-reset-tokens"))
        if remaining is not None:
            self.provider_remaining = remaining
            self.tokens_reset = now + (reset if reset is not None else 60)
        request_remaining = _header_int(headers, "x-ratelimit-remaining-requests")
        request_reset = _duration(headers.get("x-ratelimit-reset-requests"))
        if request_remaining == 0:
            self.requests_reset = now + (request_reset if request_reset is not None else 60)
        retry = _retry_after(headers)
        if status == 429:
            safe_reset = max([value for value in (retry, reset if remaining == 0 else None, request_reset if request_remaining == 0 else None) if value is not None], default=None)
            # Missing/malformed headers do not justify retrying this request. A
            # subsequent call must nevertheless allow a full local window first.
            self.blocked_until = max(self.blocked_until, now + (safe_reset if safe_reset is not None else 60))
            return safe_reset
        return None


_GUARDS: dict[str, _TokenGuard] = {}
_GUARDS_LOCK = Lock()


def _guard_for(key: str, model: str) -> _TokenGuard:
    identity = hashlib.sha256(f"{key}\0{model}".encode()).hexdigest()
    with _GUARDS_LOCK:
        return _GUARDS.setdefault(identity, _TokenGuard())


def _wait_for_reset(delay: float, deadline: float | None, max_wait: float) -> None:
    remaining = remaining_budget(deadline)
    # Leave room to actually send/read; sleeping to the deadline is not progress.
    if delay > max_wait or (remaining is not None and delay + .05 >= remaining):
        raise AIError("Groq rate-limit reset exceeds the bounded wait or remaining time budget; no further request was made.", code="rate_limit", status=429, retry_after=delay)
    sleep(delay)
    remaining_budget(deadline)


def remaining_deadline(remaining_seconds: float | None) -> float | None:
    if remaining_seconds is None:
        return None
    if not math.isfinite(remaining_seconds) or remaining_seconds <= 0:
        raise AIError("Groq remaining time budget exhausted or invalid; no request was made.", code="deadline")
    return monotonic() + remaining_seconds


def remaining_budget(deadline: float | None) -> float | None:
    if deadline is None:
        return None
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise AIError("Groq remaining time budget exhausted; no further request was made.", code="deadline")
    return remaining


def _request_timeout(remaining_seconds: float | None) -> httpx.Timeout:
    if remaining_seconds is None:
        return httpx.Timeout(35.0, connect=5.0, read=30.0, write=8.0, pool=3.0)
    # Bound the combined phase allowances, not just each individual phase. Read
    # timeouts are per chunk, so the absolute deadline is also checked on reads.
    scale = min(1.0, remaining_seconds / (5.0 + 30.0 + 8.0 + 3.0))
    return httpx.Timeout(min(35.0, remaining_seconds), connect=5.0 * scale, read=30.0 * scale, write=8.0 * scale, pool=3.0 * scale)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError("non-finite JSON value")


def structured_call(
    settings: Any,
    output_model: type[Model],
    *,
    system: str,
    user: str,
    transport: httpx.BaseTransport | None = None,
    max_tokens: int | None = None,
    remaining_seconds: float | None = None,
    on_call: Callable[[], None] | None = None,
) -> Model:
    """on_call runs once immediately before EACH HTTP attempt, including a 429.

    The callback should be fast/nonblocking and can reject budget admission by
    raising. It is not invoked for absent credentials, bad input or expired time.
    """
    deadline = remaining_deadline(remaining_seconds)
    if not settings or not getattr(settings, "groq_key", ""):
        raise AIError("Groq API key is not configured; AI extraction/matching unavailable.", code="configuration")
    model = getattr(settings, "groq_model", "")
    if not model:
        raise AIError("Groq model is not configured; AI extraction/matching unavailable.", code="configuration")
    # JSON object mode works beyond the select strict-schema models. The schema is
    # supplied explicitly and validated locally; no claim of constrained decoding.
    schema = json.dumps(_compact_schema(output_model.model_json_schema()), separators=(",", ":"))
    instruction = f"{system}\nReturn only a JSON object matching this schema:\n{schema}"
    if len(instruction) + len(user) > MAX_INPUT_CHARS:
        raise AIError("Groq input limit exceeded; no request was made.", code="input_limit")
    tpm = _integer_setting(settings, "discovery_ai_tpm", DEFAULT_TPM, 256, 10_000_000)
    output_tpm = _integer_setting(settings, "discovery_ai_output_tpm", DEFAULT_OUTPUT_TPM, 1, 10_000_000)
    output_limit = _integer_setting(settings, "discovery_ai_max_output_tokens", DEFAULT_MAX_OUTPUT, 256, 6000)
    if max_tokens is None:
        max_tokens = output_limit
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or not 1 <= max_tokens <= 6000:
        raise AIError("Groq output token budget is invalid; no request was made.", code="configuration")
    output_tokens = min(max_tokens, output_limit)
    max_wait = getattr(settings, "discovery_ai_max_wait_seconds", 65.0)
    if isinstance(max_wait, bool) or not isinstance(max_wait, (int, float)) or not math.isfinite(max_wait) or not 0 <= max_wait <= 120:
        raise AIError("Groq bounded wait configuration is invalid; no request was made.", code="configuration")
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": instruction}, {"role": "user", "content": user}],
        "response_format": {"type": "json_object"},
        "temperature": 0,
        "max_completion_tokens": output_tokens,
        "stream": False,
    }
    # This applies only to discovery's existing model, not the separate tool
    # loop or other configured models. Reasoning tokens consume output quota.
    if model == "qwen/qwen3.8-27b":
        payload["reasoning_effort"] = "none"
    guard = _guard_for(settings.groq_key, model)
    try:
        prompt_bytes = len((instruction + user).encode("utf-8"))
    except UnicodeError:
        raise AIError("Groq input text encoding is invalid; no request was made.", code="input_limit") from None
    remaining = remaining_budget(deadline)
    if not guard.lock.acquire(timeout=max(0.0, min(max_wait, remaining if remaining is not None else max_wait))):
        raise AIError("Groq shared admission slot unavailable within the time budget; no request was made.", code="rate_limit")
    # No tokenizer dependency: an intentionally conservative UTF-8 byte/3 prompt
    # estimate plus framing, corrected upward by real prompt usage when reported.
    # Provider remaining-token headers account for calls outside this process.
    estimated_prompt = math.ceil(prompt_bytes * guard.prompt_ratio) + 64
    # ITPM and OTPM are independent. Combining max output with prompt tokens
    # under the generic 8k header missed the observed separate 1k output cap.
    reservation = estimated_prompt
    waited = False
    try:
        with httpx.Client(transport=transport, timeout=_request_timeout(remaining_budget(deadline)), follow_redirects=False) as client:
            for attempt in range(2):
                delay = guard.delay(reservation, tpm, output_tokens, output_tpm)
                if delay > 0:
                    if waited:
                        raise AIError("Groq shared token budget still unavailable after one reset wait; no further request was made.", code="rate_limit", status=429, retry_after=delay)
                    _wait_for_reset(delay + .01, deadline, max_wait)
                    waited = True
                    delay = guard.delay(reservation, tpm, output_tokens, output_tpm)
                    if delay > 0:
                        raise AIError("Groq shared token budget still unavailable after one reset wait; no further request was made.", code="rate_limit", status=429, retry_after=delay)
                remaining = remaining_budget(deadline)
                client.timeout = _request_timeout(remaining)
                if on_call is not None:
                    on_call()
                    remaining_budget(deadline)
                    client.timeout = _request_timeout(remaining_budget(deadline))
                charge = _Charge(monotonic(), reservation, output_tokens)
                guard.charges.append(charge)
                if guard.provider_remaining is not None:
                    guard.provider_remaining = max(0, guard.provider_remaining - reservation)
                if guard.provider_output_remaining is not None:
                    guard.provider_output_remaining = max(0, guard.provider_output_remaining - output_tokens)
                with client.stream("POST", GROQ_ENDPOINT, headers={"Authorization": f"Bearer {settings.groq_key}", "Accept": "application/json"}, json=payload) as response:
                    old_block = guard.blocked_until
                    reset = guard.headers(response.headers, response.status_code)
                    if not 200 <= response.status_code < 300:
                        charge.tokens = charge.output_tokens = 0  # No completion on rejected requests.
                        details = _rate_details(response, deadline, output_tpm=output_tpm)
                        if details is not None:
                            if details.dimension == "output":
                                guard.provider_output_limit = min(guard.provider_output_limit or details.limit, details.limit)
                            elif details.dimension == "input":
                                guard.provider_limit = min(guard.provider_limit or details.limit, details.limit)
                            if details.requested is not None and details.requested > details.limit:
                                # Waiting cannot make a single oversized request
                                # fit; no same-payload retry or invented reset.
                                guard.blocked_until = old_block
                                code = "output_limit" if details.dimension == "output" else "input_limit" if details.dimension == "input" else "request_size"
                                raise AIError("Groq rejected a request exceeding its token limit; waiting cannot admit that request. Reduce the explicit source/output budget.", code=code,
                                    status=429, dimension=details.dimension, limit=details.limit, requested=details.requested)
                            if details.dimension == "output":
                                # Full generic headers never establish available
                                # OTPM. Header Retry-After is usable; otherwise a
                                # later new request waits a conservative minute.
                                guard.provider_output_remaining = 0
                                guard.output_reset = monotonic() + (reset if reset is not None else 60)
                        if response.status_code == 429 and reset is not None and not waited and attempt == 0:
                            # The response is closed before sleeping/re-attempting.
                            retry = reset
                        else:
                            messages = {
                                400: ("Groq rejected the structured-output request or configured model.", "request"),
                                401: ("Groq authentication failed; check the server API key.", "authentication"),
                                402: ("Groq allowance or credits are exhausted.", "quota"),
                                403: ("Groq denied the request.", "denied"),
                                429: ("Groq quota/rate limit reached; no further retry was attempted.", "rate_limit"),
                            }
                            message, code = messages.get(response.status_code, ("Groq provider returned an error; no retry was attempted.", "provider"))
                            provider_code=_request_failure_code(response,deadline)
                            if provider_code=='json_validate_failed':
                                message='Groq could not produce valid JSON within this request; retained source conditions need review.'
                                code='invalid_response'
                            elif provider_code:
                                message += ' Provider code: '+provider_code+'.'
                            raise AIError(message, code=code, status=response.status_code, retry_after=reset,
                                dimension=details.dimension if details else None, limit=details.limit if details else None, requested=details.requested if details else None)
                    else:
                        chunks: list[bytes] = []
                        size = 0
                        for chunk in response.iter_bytes():
                            remaining_budget(deadline)
                            size += len(chunk)
                            if size > MAX_RESPONSE_BYTES:
                                raise AIError("Groq response exceeded the size limit.", code="invalid_response")
                            chunks.append(chunk)
                        # Conservatively retain both charges for a full minute
                        # from completion, including slow/generated responses.
                        charge.at = monotonic()
                        break
                _wait_for_reset(retry + .01, deadline, max_wait)
                waited = True
        remaining_budget(deadline)
        envelope = json.loads(b"".join(chunks), object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
        if isinstance(envelope, dict) and isinstance(envelope.get("usage"), dict):
            usage = envelope["usage"]
            prompt, completion, total = (usage.get(key) for key in ("prompt_tokens", "completion_tokens", "total_tokens"))
            valid = lambda value: type(value) is int and 0 <= value <= 10_000_000
            if valid(prompt):
                charge.tokens = prompt
                guard.prompt_ratio = max(guard.prompt_ratio, prompt / max(1, prompt_bytes) * 1.10)
            elif valid(total):
                # Unknown allocation: total is a conservative input bound, not
                # evidence that output was free. Keep output reservation too.
                charge.tokens = total
            if valid(completion):
                # Includes Qwen reasoning tokens when the provider reports them.
                charge.output_tokens = completion
        if not isinstance(envelope, dict) or not isinstance(envelope.get("choices"), list) or not envelope["choices"]:
            raise ValueError("missing choices")
        choice = envelope["choices"][0]
        if not isinstance(choice, dict) or not isinstance(choice.get("message"), dict):
            raise ValueError("invalid completion envelope")
        if choice.get("finish_reason") not in {None, "stop"}:
            raise AIError("Groq returned an incomplete or refused structured response; requirements were not accepted. Increase the explicit output budget if needed.", code="incomplete")
        content = choice["message"].get("content")
        if not isinstance(content, str):
            raise ValueError("missing JSON content")
        value = json.loads(content, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
        return output_model.model_validate(value, strict=True)
    except httpx.TimeoutException:
        raise AIError("Groq request timed out; no retry was attempted.", code="timeout") from None
    except httpx.RequestError:
        raise AIError("Groq could not be reached; no retry was attempted.", code="network") from None
    except (ValueError, TypeError, KeyError, IndexError, ValidationError, UnicodeError):
        raise AIError("Groq returned invalid JSON or an invalid structured response; no retry was attempted.", code="invalid_response") from None
    finally:
        guard.lock.release()


def public_link(raw: str, base: str = "") -> str | None:
    """Validate supplied links without fetching them or accepting model-made URLs."""
    if not raw or len(raw) > 2000:
        return None
    try:
        url = urlsplit(urljoin(base, raw))
        host = (url.hostname or "").lower().rstrip(".")
        if url.scheme not in {"http", "https"} or not host or url.username or url.password:
            return None
        if url.port not in {None, 80, 443} or "." not in host:
            return None
        if host in {"localhost", "metadata.google.internal"} or host.endswith((".local", ".localhost", ".internal", ".test", ".invalid")):
            return None
        try:
            if not ipaddress.ip_address(host).is_global:
                return None
        except ValueError:
            if host.isdigit():
                return None
        if re.search(r"/(?:login|signin|sign-in|account|dashboard)(?:/|$)", url.path, re.I):
            return None
        if any(re.search(r"token|secret|password|api.?key|session|auth|invite", key, re.I) for key, _ in parse_qsl(url.query)):
            return None
        return urlunsplit((url.scheme, url.netloc, url.path or "/", url.query, ""))
    except ValueError:
        return None
