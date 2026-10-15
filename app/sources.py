"""Bounded public-source discovery and conservative, evidence-preserving adapters.

The deployed application calls the TinyFish REST APIs itself. Recorded examples
are an explicit user action; a provider failure never substitutes an example.
Only exact fragments in a fetched snapshot can create a supported fact.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit, urlunsplit

import httpx

from app.config import ROOT, Settings, settings as default_settings
from app.models import DiscoveryResult, Fact, Opportunity, SourceOutcome, SourceSnapshot, utc_now


SEARCH_ENDPOINT = "https://api.search.tinyfish.ai"
FETCH_ENDPOINT = "https://api.fetch.tinyfish.ai"
OIST_APPLY = "https://www.oist.jp/admissions/research-internship/apply-research-internship"
OIST_SUPPORT = "https://www.oist.jp/admissions/research-internship/program-description"
SNAPSHOT_DIR = ROOT / "data" / "source_snapshots"
MAX_DISCOVERY = 6
MAX_CONTENT_CHARS = 250_000

# Information placeholders do not invent hard conditions where none was observed.
# Missing documents, deadline, or portal state nevertheless prevent certification.
SHARED_FIELDS: dict[str, str] = {
    "application_deadline": "requirement",
    "portal_status": "information",
    "documents": "requirement",
    "reference_min": "information",
    "reference_received_before_submit": "information",
    "reference_submitter": "information",
    "reference_forbidden": "information",
    "statement_max_words": "information",
    "statement_max_chars": "information",
    "statement_max_pages": "information",
    "transcript_translation": "information",
    "document_format": "information",
    "fee_amount": "information",
    "fee_currency": "information",
    "funding": "information",
    "degree_levels": "information",
    "degree_program_types": "information",
    "fields": "information",
    "min_study_year": "information",
    "min_years_remaining": "information",
    "max_years_remaining": "information",
    "year_constraint": "information",
    "institution_approval": "information",
    "work_authorization_preference": "information",
}


class TinyFishError(RuntimeError):
    """Safe provider error, retaining successes when a batch partly fails."""

    def __init__(
        self,
        message: str,
        *,
        snapshots: list[SourceSnapshot] | None = None,
        errors: list[str] | None = None,
        source_errors: dict[str, list[str]] | None = None,
    ) -> None:
        super().__init__(message)
        self.snapshots = snapshots if snapshots is not None else []
        self.errors = errors or [message]
        self.source_errors = source_errors or {}


class _FetchedSnapshots(list[SourceSnapshot]):
    """Keep request-to-final-URL association without changing the list contract."""

    def __init__(self) -> None:
        super().__init__()
        self.by_requested_url: dict[str, SourceSnapshot] = {}


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _public_url(value: str) -> str:
    """Reject credentials, local targets and account/private URL forms.

    DNS/IP resolution and redirect safety are also enforced by TinyFish's public
    Fetch endpoint. The app never fetches target pages through its own network.
    """
    if not isinstance(value, str) or len(value) > 2000:
        raise TinyFishError("Public source URL is invalid.")
    try:
        parsed = urlsplit(value.strip())
        host = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except ValueError:
        raise TinyFishError("Public source URL is invalid.") from None
    if parsed.scheme not in {"https", "http"} or not host:
        raise TinyFishError("Source URL must use public HTTP or HTTPS.")
    if parsed.username or parsed.password:
        raise TinyFishError("Source URL cannot contain credentials.")
    if port is not None and port not in {80, 443}:
        raise TinyFishError("Only public web ports are supported.")
    if host in {"localhost", "metadata.google.internal"} or host.endswith(
        (".localhost", ".local", ".internal", ".test", ".invalid")
    ):
        raise TinyFishError("Local or private source URLs are not allowed.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if "." not in host or host.isdigit():
            raise TinyFishError("Local or private source URLs are not allowed.") from None
    else:
        if not address.is_global:
            raise TinyFishError("Local or private source URLs are not allowed.")
    if re.search(r"/(?:login|log-in|signin|sign-in|account|dashboard|my-account)(?:/|$)", parsed.path, re.I):
        raise TinyFishError("Login and account pages are not public sources.")
    if any(
        re.search(r"(?:token|secret|password|api[_-]?key|session|auth|invite)", key, re.I)
        for key, _ in parse_qsl(parsed.query, keep_blank_values=True)
    ):
        raise TinyFishError("Private or token-bearing source URLs are not allowed.")
    # Remove fragments without changing query semantics or page text.
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, ""))


def _same_host(url: str, domain: str) -> bool:
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    return host == domain or host.endswith("." + domain)


def _safe_url_label(url: str) -> str:
    try:
        return _public_url(url)
    except TinyFishError:
        return "rejected source URL"


class TinyFishClient:
    def __init__(
        self,
        settings: Settings = default_settings,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.transport = transport

    def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        if not self.settings.tinyfish_key:
            raise TinyFishError("TinyFish API key is not configured on the server.")
        # The provider has its own 25-second per-URL deadline. We intentionally
        # stop at 40 seconds rather than use its 110-second default.
        timeout = httpx.Timeout(40.0, connect=8.0, read=35.0, write=8.0, pool=3.0)
        try:
            with httpx.Client(
                headers={"X-API-Key": self.settings.tinyfish_key, "Accept": "application/json"},
                timeout=timeout,
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                response = client.request(method, url, **kwargs)
        except httpx.TimeoutException:
            raise TinyFishError("TinyFish request timed out; previous source evidence was not refreshed.") from None
        except httpx.RequestError:
            raise TinyFishError("TinyFish could not be reached; previous source evidence was not refreshed.") from None
        messages = {
            400: "TinyFish rejected the request.",
            401: "TinyFish authentication failed; check the server API key.",
            402: "TinyFish free allowance or credits are exhausted; wait for reset or review the provider account.",
            403: "TinyFish denied access to this public-source request.",
            404: "TinyFish endpoint is unavailable.",
            422: "TinyFish rejected the extraction options.",
            429: "TinyFish rate limit reached; retry later.",
        }
        if not 200 <= response.status_code < 300:
            raise TinyFishError(messages.get(response.status_code, "TinyFish provider returned an error."))
        try:
            data = response.json()
        except (ValueError, UnicodeError):
            raise TinyFishError("TinyFish returned an invalid JSON response.") from None
        if not isinstance(data, dict):
            raise TinyFishError("TinyFish returned an unexpected response shape.")
        return data

    def search(self, query: str) -> dict[str, Any]:
        if not isinstance(query, str) or not query.strip() or len(query) > 500:
            raise TinyFishError("Discovery query must contain 1–500 characters.")
        data = self._request(
            "GET",
            SEARCH_ENDPOINT,
            params={
                "query": query.strip(),
                "language": "en",
                "purpose": "Find primary public internship program or employer application pages with eligibility and application information.",
            },
        )
        if not isinstance(data.get("results"), list):
            raise TinyFishError("TinyFish search response has no result list.")
        return data

    def fetch(self, urls: list[str]) -> list[SourceSnapshot]:
        if not isinstance(urls, list) or not 1 <= len(urls) <= 10:
            raise TinyFishError("Fetch needs 1–10 public source URLs.")
        chosen = list(dict.fromkeys(_public_url(url) for url in urls))
        data = self._request(
            "POST",
            FETCH_ENDPOINT,
            json={
                "urls": chosen,
                "format": "markdown",
                "links": False,
                "image_links": False,
                "iframe_links": False,
                "ttl": 0,
                "per_url_timeout_ms": 25_000,
            },
        )
        if not isinstance(data.get("results"), list) or not isinstance(data.get("errors", []), list):
            raise TinyFishError("TinyFish fetch returned an unexpected response shape.")
        checked_at = utc_now()
        snapshots = _FetchedSnapshots()
        errors: list[str] = []
        source_errors: dict[str, list[str]] = {}
        returned: set[str] = set()

        def failure(url: str, message: str) -> None:
            errors.append(message)
            source_errors.setdefault(url, []).append(message)

        for row in data["results"]:
            if not isinstance(row, dict):
                errors.append("TinyFish returned a malformed page result.")
                continue
            original = row.get("url")
            if original not in chosen:
                errors.append("TinyFish returned an unrequested source; it was ignored.")
                continue
            returned.add(original)
            try:
                final_url = _public_url(row.get("final_url") or original)
            except TinyFishError:
                failure(original, f"Public fetch rejected redirect for {_safe_url_label(original)}.")
                continue
            content = row.get("text")
            if not isinstance(content, str) or not content.strip():
                failure(original, f"Public fetch returned no readable text for {_safe_url_label(original)}.")
                continue
            if len(content) > MAX_CONTENT_CHARS:
                failure(original, f"Public source is too large for bounded extraction: {_safe_url_label(original)}.")
                continue
            # Account-wall text is never a valid snapshot or an opportunity.
            if re.search(r"(?:sign in|log in|login) (?:is )?required to (?:view|access)|please (?:sign in|log in) to (?:view|access)", content, re.I):
                failure(original, f"Public fetch encountered a login wall at {_safe_url_label(original)}.")
                continue
            snapshot = SourceSnapshot(
                id="source-" + _hash(final_url)[:16],
                url=final_url,
                title=row.get("title") if isinstance(row.get("title"), str) else "",
                text=content,
                checked_at=checked_at,
                content_hash=_hash(content),
                mode="live",
            )
            snapshots.append(snapshot)
            snapshots.by_requested_url[original] = snapshot
        allowed_errors = {
            "target_http_error", "page_not_found", "target_unreachable", "timeout", "bot_blocked",
            "empty_content", "login_required", "content_too_large", "invalid_url", "invalid_redirect_url",
            "proxy_error", "conditional_unsupported", "selector_not_matched", "selector_unsupported",
        }
        for row in data.get("errors", []):
            if not isinstance(row, dict):
                errors.append("Public source fetch failed (malformed error detail).")
                continue
            original = row.get("url")
            if original in chosen:
                returned.add(original)
            code = row.get("error")
            if not isinstance(code, str) or code not in allowed_errors:
                code = "source_failure"
            # Never echo a provider error message or authentication response body.
            message = f"Public source fetch failed ({code}): {_safe_url_label(original or '')}."
            if original in chosen:
                failure(original, message)
            else:
                errors.append(message)
        for url in chosen:
            if url not in returned:
                failure(url, f"TinyFish returned no result for {url}.")
        if errors:
            raise TinyFishError("Some public sources could not be refreshed.", snapshots=snapshots,
                                errors=errors, source_errors=source_errors)
        return snapshots


class _Facts:
    def __init__(self, snapshot: SourceSnapshot) -> None:
        self.snapshot = snapshot
        self.values = {
            name: Fact(name=name, kind=kind, source_url=snapshot.url, source_id=snapshot.id,
                       simulated=snapshot.mode == "synthetic")
            for name, kind in SHARED_FIELDS.items()
        }

    def match(self, pattern: str, *, flags: int = re.I | re.S) -> re.Match[str] | None:
        return re.search(pattern, self.snapshot.text, flags)

    def add(
        self, name: str, value: Any, excerpt: str, *, kind: str = "requirement", status: str = "known"
    ) -> None:
        if not excerpt or excerpt not in self.snapshot.text:
            raise ValueError(f"Evidence for {name} must be a nonempty exact source fragment.")
        prior = self.values.get(name)
        if prior and prior.status in {"known", "conflicting"} and prior.value != value:
            # Both observations remain in one exact source span for inspection.
            start = min(self.snapshot.text.index(prior.excerpt), self.snapshot.text.index(excerpt))
            end = max(self.snapshot.text.index(prior.excerpt) + len(prior.excerpt), self.snapshot.text.index(excerpt) + len(excerpt))
            excerpt = self.snapshot.text[start:end]
            value = None
            status = "conflicting"
        self.values[name] = Fact(
            name=name, value=value, status=status, kind=kind, excerpt=excerpt,
            source_url=self.snapshot.url, source_id=self.snapshot.id,
            simulated=self.snapshot.mode == "synthetic",
        )

    def from_pattern(self, name: str, pattern: str, value: Any, *, kind: str = "requirement") -> None:
        found = self.match(pattern)
        if found:
            self.add(name, value, found.group(0), kind=kind)

    def list(self) -> list[Fact]:
        return list(self.values.values())


MONTHS = {name.lower(): index for index, name in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], 1
)}
MONTH_PATTERN = "(?:" + "|".join(MONTHS) + ")"
DATE_PATTERN = rf"(?:{MONTH_PATTERN}\s+\d{{1,2}}(?:st|nd|rd|th)?[,]?\s+\d{{4}}|\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTH_PATTERN}\s+\d{{4}})"


def _date_from_fragment(fragment: str, *, end_of_day: bool = False) -> datetime | None:
    date = re.search(DATE_PATTERN, fragment, re.I)
    if not date:
        return None
    cleaned = re.sub(r"(\d)(?:st|nd|rd|th)\b", r"\1", date.group(0), flags=re.I).replace(",", "")
    parts = cleaned.lower().split()
    if parts[0] in MONTHS:
        month, day, year = MONTHS[parts[0]], int(parts[1]), int(parts[2])
    else:
        day, month, year = int(parts[0]), MONTHS[parts[1]], int(parts[2])
    time_match = re.search(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b", fragment)
    if time_match:
        hour, minute, second = int(time_match[1]), int(time_match[2]), int(time_match[3] or 0)
    elif end_of_day:
        hour, minute, second = 23, 59, 59
    else:
        return None
    if re.search(r"\b(?:JST|UTC\s*\+\s*9)\b", fragment, re.I):
        zone = timezone(timedelta(hours=9))
    elif re.search(r"\b(?:AOE|anywhere on earth)\b", fragment, re.I):
        zone = timezone(timedelta(hours=-12))
    elif re.search(r"\b(?:UTC|GMT)\b(?!\s*[+-])", fragment, re.I):
        zone = timezone.utc
    else:
        offset = re.search(r"\b(?:UTC|GMT)\s*([+-])(\d{1,2})(?::(\d{2}))?", fragment, re.I)
        if not offset:
            return None
        if int(offset[2]) >= 24 or int(offset[3] or 0) >= 60:
            return None
        total = int(offset[2]) * 60 + int(offset[3] or 0)
        zone = timezone(timedelta(minutes=total if offset[1] == "+" else -total))
    try:
        return datetime(year, month, day, hour, minute, second, tzinfo=zone)
    except ValueError:
        return None


def _portal(facts: _Facts, *, cohort: str = "") -> str:
    # Labels such as APPLY NOW and a scheduled deadline are not portal observations.
    observations: list[tuple[str, str]] = []
    closed = facts.match(r"Applications?\s+(?:are\s+)?(?:now\s+)?CLOSED\b[^\n.!]*[.!]?", flags=re.I)
    if closed:
        observations.append(("closed", closed.group(0)))
    concluded = facts.match(r"The\s+[^\n]+?call for[^\n]+?applications has now concluded[^\n]*", flags=re.I)
    if concluded and (not cohort or cohort.lower() in concluded.group(0).lower()):
        observations.append(("closed", concluded.group(0)))
    opened = facts.match(r"Applications?\s+(?:are\s+)?(?:now\s+)?OPEN(?:\s+for\s+[^\n.!]+)?[.!]?", flags=re.I)
    if opened:
        observations.append(("open", opened.group(0)))
    for state, excerpt in observations:
        facts.add("portal_status", state, excerpt, kind="information")
    status = facts.values["portal_status"]
    return status.value if status.status == "known" else "unknown"


def _opportunity(
    snapshot: SourceSnapshot, facts: _Facts, *, identifier: str, program: str, cycle: str,
    country: str, category: str = "Research", summary: str = "",
) -> Opportunity:
    portal = facts.values["portal_status"]
    state = portal.value if portal.status == "known" else "unknown"
    deadline = facts.values["application_deadline"]
    if deadline.status == "known" and deadline.value:
        try:
            if datetime.fromisoformat(deadline.value) < datetime.now(timezone.utc):
                state = "closed"
        except (ValueError, TypeError):
            state = "unknown"
    # A contradiction cannot be certified even when another fact looks complete.
    verification = "partial"
    if any(f.status == "conflicting" for f in facts.list()):
        verification = "uncertain"
    elif all(facts.values[name].status == "known" for name in ("documents", "application_deadline", "portal_status")):
        verification = "verified"
    return Opportunity(
        id=identifier, program=program, cycle=cycle, category=category, country=country,
        source_url=snapshot.url, checked_at=snapshot.checked_at, call_status=state,
        verification=verification, mode=snapshot.mode, facts=facts.list(), summary=summary,
    )


def _epfl(snapshot: SourceSnapshot) -> list[Opportunity]:
    facts = _Facts(snapshot)
    deadline = facts.match(r"The next deadline is\s+[^\n]*\n?[^\n]*?\b20\d{2}\s*\([^\n]+?\)\s+for internships in summer\s+(20\d{2})\.?")
    cycle_year = deadline.group(1) if deadline else None
    if not cycle_year:
        cycle = facts.match(r"(?:internships? in|for)\s+summer\s+(20\d{2})")
        cycle_year = cycle.group(1) if cycle else None
    cycle = f"Summer {cycle_year}" if cycle_year else "unknown"
    if deadline:
        parsed = _date_from_fragment(deadline.group(0))
        facts.add("application_deadline", parsed.isoformat() if parsed else None, deadline.group(0),
                  status="known" if parsed else "unknown")
    _portal(facts)
    docs = facts.match(r"upload three documents:\s*a CV,\s*your transcripts,\s*and a letter of motivation[^.]*\.")
    if not docs:
        docs = facts.match(r"You will need to upload[^\n]+\bCV\b.*?letter of motivation.*?(?:two pages|pages)\)\.")
    if docs:
        facts.add("documents", ["cv", "transcript", "statement"], docs.group(0))
    refs = facts.match(r"No, we do not need nor consider recommendation letters[^.]*\..*?uploading\s+letters of reference could jeopardize your application\.")
    if refs:
        facts.add("reference_min", 0, refs.group(0))
        facts.add("reference_forbidden", True, refs.group(0))
    facts.from_pattern("statement_max_pages", r"not longer than two pages", 2)
    facts.from_pattern("document_format", r"The only format we support is PDF\.", "pdf")
    facts.from_pattern("transcript_translation", r"If\s+they are not in English,.*?translation.*?you can do it yourself\)\.", "self")
    degree = facts.match(r"To be eligible, you must be still enrolled in a Bachelor or a Master\s+programme at the time of the fellowship\.")
    if degree:
        facts.add("degree_levels", ["bachelor", "master"], degree.group(0))
        facts.add("enrolled_at_internship", True, degree.group(0))
    domain = facts.match(r"No, this programme is only for the School of Computer and Communication Sciences\..*?please discuss this\s+clearly in the letter of motivation\.")
    if domain:
        facts.add("fields", ["computer_science", "communication_sciences"], domain.group(0))
        facts.add("field_evidence_exception", True, domain.group(0), kind="information")
    facts.from_pattern("excluded_home_institution", r"No, this programme is only for students from other institutions\.", "EPFL")
    return [_opportunity(
        snapshot, facts, identifier=f"epfl-summer-{cycle_year}" if cycle_year else "epfl-unscoped-" + _hash(snapshot.url)[:10],
        program="Summer@EPFL", cycle=cycle, country="Switzerland",
        summary="Scientific domains and final motivation letter are program-specific. Opening has no exact confirmed date.",
    )]


def _oist_shared(snapshot: SourceSnapshot) -> _Facts:
    facts = _Facts(snapshot)
    documents = facts.match(r"# Application Documents\s+.*?(?=\n# Application Fee|\Z)")
    if documents:
        doc_names = [
            ("Transcript", "transcript"), ("Statement of Purpose", "statement"),
            ("Curriculum Vitae", "cv"), ("Recommendation Letter", "reference"),
            ("Passport", "identity_document"), ("ID Photo", "id_photo"),
        ]
        names = [
            name for phrase, name in doc_names
            if re.search(rf"(?:^|\n)\s*\d+\.\s+\*?\*?{re.escape(phrase)}", documents.group(0), re.I)
        ]
        if "certificate of enrollment" in documents.group(0).lower() or "completed diploma" in documents.group(0).lower():
            names.append("diploma_or_enrollment")
        # An incomplete/empty document section is not evidence that omitted
        # requirements were withdrawn. Keep completeness unknown in that case.
        if {"transcript", "statement", "cv", "reference", "identity_document", "id_photo", "diploma_or_enrollment"} <= set(names):
            facts.add("documents", names, documents.group(0))
    refs = facts.match(r"Applicants must submit\s+(\d+)\s+to\s+(\d+) letters of recommendation[^.]*\..*?postdocs are not eligible\.")
    if refs:
        facts.add("reference_min", int(refs[1]), refs.group(0))
        facts.add("reference_max", int(refs[2]), refs.group(0))
        facts.add("reference_submitter", "professorial_level_faculty", refs.group(0))
    receipt = facts.match(r"You may submit your application only after at least one recommendation letter is received[^.]*\..*?does not accept direct submissions from applicants\.")
    if receipt:
        facts.add("reference_received_before_submit", True, receipt.group(0))
        facts.add("applicant_reference_upload_allowed", False, receipt.group(0))
    for m in re.finditer(r"no more than\s+(\d+)\s+words\s*\((\d+)\s+characters\)", snapshot.text, re.I):
        facts.add("statement_max_words", int(m[1]), m.group(0))
        facts.add("statement_max_chars", int(m[2]), m.group(0))
    facts.from_pattern("document_format", r"prepare all required documents in English, save them as a PDF file", "pdf")
    facts.from_pattern("transcript_translation", r"English explanation is required for transcripts that are not written in English\.", "english_explanation")
    fee = facts.match(r"application fee[^\n.]*?\*?\*?([\d,]+)\s+JPY\*?\*?\.")
    if fee:
        facts.add("fee_amount", int(fee[1].replace(",", "")), fee.group(0), kind="information")
        facts.add("fee_currency", "JPY", fee.group(0), kind="information")
    eligibility = facts.match(r"Those who are currently enrolled.*?(?=\n\nCurrently enrolled|\n\nOur Research|\n#)")
    if eligibility and "last two years" in eligibility.group(0).lower():
        levels = [
            level for level in ("bachelor", "master")
            if re.search(rf"\b{level}.?s degree", eligibility.group(0), re.I)
        ]
        facts.add("degree_levels", levels, eligibility.group(0))
        # "Last two years" is an ordinal-year constraint, not two years after
        # completing the current year. The structured rule owns assessment.
        facts.add("max_years_remaining", 2, eligibility.group(0), kind="information")
        facts.add("year_constraint", {
            "type": "final_two_years", "applies_to": ["bachelor"],
            "assessed_at": "application_or_internship_start",
            "graduates_allowed": True if "those who have graduated" in eligibility.group(0).lower() else None,
        }, eligibility.group(0))
    facts.from_pattern("institution_approval", r"Currently enrolled students must have approval from their home institution\.", True)
    facts.from_pattern("host_unit_background", r"The academic background of applicants should be appropriate to their desired host unit\(s\) at OIST\.", "appropriate_to_selected_unit")
    facts.from_pattern("excluded_degree_levels", r"Current or graduated PhD students are not eligible[^.]*\.", ["phd"])
    facts.from_pattern("english_score_optional", r"An English Proficiency Score[^\n]*?is not required[^.]*\.", True, kind="information")
    return facts


def _oist(snapshot: SourceSnapshot) -> list[Opportunity]:
    # Round identity survives a removed/changed deadline cell. Otherwise a
    # successful partial extraction would hide that existing cohort entirely.
    rounds = list(re.finditer(
        r"\|\s*(Spring|Fall)\s+(20\d{2})\s+Internship\s*\|\s*([^|\n]*)\|([^\n]*)", snapshot.text, re.I,
    ))
    opportunities: list[Opportunity] = []
    for row in rounds:
        facts = _oist_shared(snapshot)
        season, year = row[1].lower(), row[2]
        deadline = _date_from_fragment(row[3])
        facts.add("application_deadline", deadline.isoformat() if deadline else None, row.group(0),
                  status="known" if deadline else "unknown")
        facts.add("application_round", f"{season.title()} {year}", row.group(0), kind="information")
        period = row[4].split("|")
        if len(period) >= 2:
            facts.add("internship_period", period[1].strip(), row.group(0), kind="information")
        # Generic application buttons are not evidence that either named round
        # is open. Only a cycle-specific status declaration can establish that.
        for state in re.finditer(rf"(?:{season}\s+{year}[^\n.!]*?applications?\s+(?:are\s+)?(?:now\s+)?(open|closed)|applications?\s+for\s+{season}\s+{year}\s+(?:are\s+)?(?:now\s+)?(open|closed))\b", snapshot.text, re.I):
            facts.add("portal_status", (state[1] or state[2]).lower(), state.group(0), kind="information")
        facts.from_pattern("schedule_tentative", r"The schedule is tentative and subject to change", True, kind="information")
        opportunities.append(_opportunity(
            snapshot, facts, identifier=f"oist-{season}-{year}", program="OIST Research Internship",
            cycle=f"{season.title()} {year}", country="Japan",
            summary="Faculty recommendation must be received before submission. Portal opening is unknown unless the source names this round as open.",
        ))
    if not opportunities:
        facts = _oist_shared(snapshot)
        opportunities.append(_opportunity(
            snapshot, facts, identifier="oist-unscoped-" + _hash(snapshot.url)[:10],
            program="OIST Research Internship", cycle="unknown", country="Japan",
            summary="No supported application round and timezone-aware deadline were found in this snapshot.",
        ))
    return opportunities


def _google(snapshot: SourceSnapshot) -> list[Opportunity]:
    facts = _Facts(snapshot)
    title = re.search(r"Forward Deployed Engineer Intern,?\s+(20\d{2})", snapshot.title + "\n" + snapshot.text, re.I)
    year = title[1] if title else None
    window = facts.match(r"The anticipated application window is open from\s+(\w+)\s+(\d{1,2})\s*[-–]\s*(\w+)\s+(\d{1,2}),\s*(20\d{2})[^.]*\.")
    if window:
        try:
            start = datetime(int(window[5]), MONTHS[window[1].lower()], int(window[2])).date().isoformat()
            end = datetime(int(window[5]), MONTHS[window[3].lower()], int(window[4])).date().isoformat()
        except (ValueError, KeyError):
            pass
        else:
            facts.add("application_window_start", start, window.group(0), kind="information")
            facts.add("application_window_end", end, window.group(0), kind="information")
            # A date-only anticipated window is deliberately not an exact deadline.
            facts.add("application_deadline", None, window.group(0), status="unknown")
            facts.add("rolling_early_close", True, window.group(0), kind="information")
    facts.from_pattern("work_authorization_preference", r"Google will be prioritizing applicants who have a current right to work in Singapore[^.]*\.", "current_right_to_work_singapore_without_sponsorship", kind="preference")
    degree = facts.match(r"Currently pursuing a Bachelor.?s or Master.?s degree in Computer Science, Engineering, or a related technical field\.")
    if degree:
        facts.add("degree_levels", ["bachelor", "master"], degree.group(0))
        facts.add("fields", ["computer_science", "engineering", "related_technical"], degree.group(0))
    facts.from_pattern("year_constraint", r"Enrolled in the penultimate academic year of a Bachelor.?s or Master.?s degree\.", {
        "type": "penultimate", "applies_to": ["bachelor", "master"], "assessed_at": "application",
    })
    facts.from_pattern("on_site_location", r"Participation in the internship program requires that you are located in Singapore[^.]*\.", "Singapore")
    facts.from_pattern("english_proficiency", r"English proficiency is a requirement for this internship program\.", True)
    minimum = facts.match(r"### Minimum qualifications:\s*(.*?)(?=\n\s*### Preferred qualifications|\Z)")
    if minimum:
        for name, pattern in [
            ("software_development_experience", r"Experience with software development[^\n]*"),
            ("data_cloud_ai_experience", r"Relevant practical or internship based experience[^\n]*"),
        ]:
            m = re.search(pattern, minimum.group(0), re.I)
            if m:
                facts.add(name, True, m.group(0))
    preferred = facts.match(r"### Preferred qualifications:\s*(.*?)(?=\n\s*### About the job|\Z)")
    if preferred:
        facts.add("preferred_qualifications", preferred.group(1).strip(), preferred.group(0), kind="preference")
    facts.from_pattern("funding", r"unique 10-12 week paid internship[^.]*\.", ["paid_internship"], kind="information")
    closed = facts.match(r"(?:This role|This job|Applications)\s+(?:is|are)\s+(?:now\s+)?closed[^.\n]*[.]?", flags=re.I)
    if closed:
        facts.add("portal_status", "closed", closed.group(0), kind="information")
    return [_opportunity(
        snapshot, facts, identifier=f"google-fde-{year}" if year else "google-fde-unscoped-" + _hash(snapshot.url)[:10],
        program="Google Forward Deployed Engineer Intern", cycle=year or "unknown", country="Singapore", category="Company",
        summary="Rolling anticipated window may close early. Work authorization is a preference; exact deadline and application documents remain unverified.",
    )]


def _mitacs(snapshot: SourceSnapshot) -> list[Opportunity]:
    facts = _Facts(snapshot)
    cohort = facts.match(r"call for\s+\*?\*?Summer\s+(20\d{2})\*?\*?\s+student applications")
    if not cohort:
        cohort = facts.match(r"Eligibility requirements for\s+(20\d{2})")
    year = cohort[1] if cohort else None
    _portal(facts, cohort=f"Summer {year}" if year else "")
    documents = facts.match(r"Students must complete all the mandatory fields[^\n]*.*?A copy of their r[eé]sum[eé]/CV[^\n]*")
    if documents and all(re.search(term, documents.group(0), re.I) for term in (r"reference letter", r"transcripts", r"r[eé]sum[eé]/CV")):
        facts.add("documents", ["cv", "transcript", "reference"], documents.group(0))
    refs = facts.match(r"At least one reference letter in either English or French from a professor[^\n]*")
    if refs:
        facts.add("reference_min", 1, refs.group(0))
        facts.add("reference_submitter", "professor", refs.group(0))
    facts.from_pattern("transcript_translation", r"Their official transcripts in English and/or French.*?translated and notarized transcript[^\n]*", "notarized")
    degree = facts.match(r"Be\s+\*?\*?enrolled\*?\*?\s+in a full-time undergraduate or combined undergraduate/master.s program at an eligible institution[^\n]*")
    if degree:
        facts.add("degree_levels", ["bachelor", "combined_bachelor_master"], degree.group(0))
        facts.add("institution_listed", True, degree.group(0))
    india = facts.match(r"\*\*India\*\*\s*-\s*(20\d{2}) Cohort Eligibility(.*?)(?=\n(?:\*\*)?Ireland|\n\*\*[A-Z][a-z]+\*\*\s*-|\Z)")
    if india and year and india[1] == year:
        # Only the India-specific record is in scope for the synthetic India
        # profile. Rules from other partner blocks must never overwrite it.
        facts.add("eligibility_scope", "India", india.group(0), kind="information")
        for name, pattern, value in [
            ("citizenship_requirement", r"Citizenship requirement:\*?\*?\s*Yes; Indian Nationals only", "India"),
            ("excluded_institution_types", r"applicants from Indian Institutes of Technology \(IITs\) are not eligible[^\n]*", ["iit"]),
            ("institution_listed", r"If your institution is not listed, you are not eligible to apply\.", True),
            ("minimum_grade_percent", r"Minimum cumulative grade point average:\*?\*?\s*\*?(\d+)%\*?", None),
        ]:
            m = re.search(pattern, india.group(0), re.I)
            if m:
                facts.add(name, int(m[1]) if name == "minimum_grade_percent" else value, m.group(0))
        degree_programs = re.search(r"Eligible discipline:\*?\*?\s*\n\s*\n\* Engineering \(B.E\) and\s*\n\* Technology \(B\. Tech\)", india.group(0), re.I)
        if degree_programs:
            # B.E. and B.Tech describe degree programs. They are not academic
            # disciplines that a computer-science student must match verbatim.
            facts.add("degree_program_types", ["be", "btech"], degree_programs.group(0))
    funding = facts.match(r"## Funding\s*(.*?)(?=\n## Eligibility|\Z)")
    if funding:
        facts.add("funding", funding.group(1).strip(), funding.group(0), kind="information")
    return [_opportunity(
        snapshot, facts, identifier=f"mitacs-summer-{year}" if year else "mitacs-unscoped-" + _hash(snapshot.url)[:10],
        program="Mitacs Globalink Research Internship", cycle=f"Summer {year}" if year else "unknown", country="Canada",
        summary="Closed-call example; India partner restrictions are scoped explicitly. Institution list membership remains an applicant check.",
    )]


def parse_snapshot(snapshot: SourceSnapshot) -> list[Opportunity]:
    """Parse supported official sources; unknown pages keep unknown facts.

    Identity comes from the source's stated cohort, never the local year. Dates
    without an explicit time and zone cannot become an exact application deadline.
    """
    try:
        url = _public_url(snapshot.url)
    except TinyFishError:
        return []
    if not snapshot.text.strip():
        return []
    path = urlsplit(url).path.lower()
    if _same_host(url, "summer.epfl.ch") and (path.endswith("apply.html") or "Summer@EPFL" in snapshot.text):
        return _epfl(snapshot)
    if _same_host(url, "oist.jp") and "research-internship" in path:
        if "program-description" in path:
            return []  # A supporting page has no independently identified call.
        if "apply-research-internship" in path:
            return _oist(snapshot)
    if _same_host(url, "mitacs.ca") and "globalink-research-internship-students" in path:
        return _mitacs(snapshot)
    if _same_host(url, "google.com") and "/careers/" in path and re.search(r"Forward Deployed Engineer Intern", snapshot.text, re.I):
        return _google(snapshot)
    facts = _Facts(snapshot)
    return [_opportunity(
        snapshot, facts, identifier="source-" + _hash(url)[:16],
        program=snapshot.title or (urlsplit(url).hostname or "Public opportunity source"),
        cycle="unknown", country="Unknown", category="Company" if "/jobs/" in path or "/careers/" in path else "Research",
        summary="Public search result; this page has no supported adapter. Cohort, call status, documents and eligibility need review.",
    )]


def _application_url(url: str) -> str:
    """Follow a known official program's public application page from a result."""
    if _same_host(url, "summer.epfl.ch"):
        return "https://summer.epfl.ch/apply.html"
    if _same_host(url, "oist.jp") and "research-internship" in urlsplit(url).path:
        return OIST_APPLY
    if _same_host(url, "mitacs.ca") and "globalink-research-internship" in urlsplit(url).path:
        return "https://www.mitacs.ca/our-programs/globalink-research-internship-students/"
    return url


def _enrich_oist(opportunities: list[Opportunity], snapshots: list[SourceSnapshot]) -> None:
    support = next((s for s in snapshots if _same_host(s.url, "oist.jp") and "program-description" in urlsplit(s.url).path), None)
    if not support:
        return
    match = re.search(r"# Support\s*(.*?)(?=\nAPPLY NOW|\Z)", support.text, re.I | re.S)
    if not match:
        return
    excerpt = match.group(0)
    funding = Fact(
        name="funding", value=match.group(1).strip(), status="known", kind="information",
        excerpt=excerpt, source_url=support.url, source_id=support.id, simulated=support.mode == "synthetic",
    )
    for opportunity in opportunities:
        if opportunity.id.startswith("oist-"):
            opportunity.facts = [funding.model_copy(deep=True) if fact.name == "funding" else fact for fact in opportunity.facts]


class DiscoverService:
    def __init__(
        self,
        settings: Settings = default_settings,
        *,
        client: TinyFishClient | None = None,
        snapshot_dir: Path = SNAPSHOT_DIR,
    ) -> None:
        self.settings = settings
        self.client = client or TinyFishClient(settings)
        self.snapshot_dir = Path(snapshot_dir)

    def _fetch(self, query: str, urls: list[str], *, limit: int = MAX_DISCOVERY) -> DiscoveryResult:
        source_errors: dict[str, list[str]] = {}
        try:
            snapshots = self.client.fetch(urls)
            errors: list[str] = []
        except TinyFishError as error:
            snapshots, errors = error.snapshots, error.errors
            source_errors = error.source_errors
        opportunities: list[Opportunity] = []
        parsed_by_url: dict[str, list[Opportunity]] = {}
        extraction_errors: dict[str, list[str]] = {}
        for snapshot in snapshots:
            try:
                extracted = parse_snapshot(snapshot)
            except (ValueError, TypeError, IndexError):
                # A changed page format is missing evidence, not a certifiable
                # unchanged source and not an exception body to show the user.
                extracted = []
                message = f"Public source extraction could not read the application details: {snapshot.url}."
                extraction_errors.setdefault(snapshot.url, []).append(message)
                errors.append(message)
            if any("-unscoped-" in item.id for item in extracted):
                message = f"Public source extraction could not identify an application cohort: {snapshot.url}."
                extraction_errors.setdefault(snapshot.url, []).append(message)
                errors.append(message)
            parsed_by_url[snapshot.url] = extracted
            opportunities.extend(extracted)
        _enrich_oist(opportunities, snapshots)
        by_request = getattr(snapshots, "by_requested_url", {})
        by_url = {snapshot.url: snapshot for snapshot in snapshots}
        outcomes: list[SourceOutcome] = []
        for url in dict.fromkeys(urls):
            snapshot = by_request.get(url) or by_url.get(url)
            failures = source_errors.get(url, [])
            if snapshot is None:
                # An HTTP-level failure applies to every requested source.
                # Per-URL failures retain their own safe error summaries.
                failures = failures or errors or [f"TinyFish returned no result for {url}."]
                outcomes.append(SourceOutcome(url=url, status="failed", errors=list(failures)))
                continue
            extracted = parsed_by_url.get(snapshot.url, [])
            partial = extraction_errors.get(snapshot.url, [])
            support_only = _same_host(snapshot.url, "oist.jp") and "program-description" in urlsplit(snapshot.url).path
            if not extracted and not support_only and not partial:
                message = f"Public source extraction returned no application records: {snapshot.url}."
                partial = [message]
                errors.append(message)
            outcomes.append(SourceOutcome(
                url=url, status="failed" if failures else "partial" if partial else "success",
                opportunity_ids=list(dict.fromkeys(item.id for item in extracted)),
                errors=list(failures) + list(partial),
            ))
        # A repeated official URL or support page never creates duplicate calls.
        # The URL limit bounds provider work. Every valid cohort from those
        # fetched pages must reach ingestion even if a UI later limits cards.
        by_id = {item.id: item for item in opportunities}
        return DiscoveryResult(query=query, opportunities=list(by_id.values()), snapshots=list(snapshots),
                               source_outcomes=outcomes, errors=errors, mode="live")

    def discover(self, query: str, limit: int = 4) -> DiscoveryResult:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_DISCOVERY:
            return DiscoveryResult(query=query, errors=["Discovery limit must be between 1 and 6."], mode="live")
        try:
            results = self.client.search(query)
        except TinyFishError as error:
            return DiscoveryResult(query=query, errors=error.errors, mode="live")
        urls: list[str] = []
        errors: list[str] = []
        for row in results.get("results", []):
            if not isinstance(row, dict) or not isinstance(row.get("url"), str):
                continue
            try:
                url = _application_url(_public_url(row["url"]))
            except TinyFishError:
                errors.append("One discovery result was not a public source and was ignored.")
                continue
            if url not in urls:
                urls.append(url)
            if len(urls) >= limit:
                break
        if not urls:
            return DiscoveryResult(query=query, errors=errors + ["No usable public source URLs were returned by live search."], mode="live")
        if OIST_APPLY in urls:
            urls.append(OIST_SUPPORT)
        result = self._fetch(query, urls, limit=limit)
        result.errors = errors + result.errors
        return result

    def refresh(self, url: str) -> DiscoveryResult:
        try:
            selected = _application_url(_public_url(url))
        except TinyFishError as error:
            return DiscoveryResult(query="source refresh", errors=error.errors, mode="live")
        urls = [selected, OIST_SUPPORT] if selected == OIST_APPLY else [selected]
        return self._fetch("source refresh", urls)

    def load_examples(self) -> DiscoveryResult:
        snapshots: list[SourceSnapshot] = []
        errors: list[str] = []
        for file in sorted(self.snapshot_dir.glob("*.json")):
            try:
                raw = json.loads(file.read_text(encoding="utf-8"))
                snapshot = SourceSnapshot.model_validate(raw)
                _public_url(snapshot.url)
                checked = datetime.fromisoformat(snapshot.checked_at.replace("Z", "+00:00"))
                if checked.tzinfo is None or not snapshot.text.strip():
                    raise ValueError("Missing original checked time or content")
                if snapshot.content_hash != _hash(snapshot.text):
                    raise ValueError("Snapshot hash mismatch")
                snapshots.append(snapshot.model_copy(update={"mode": "cached"}))
            except (ValueError, OSError, TinyFishError):
                errors.append(f"Recorded public snapshot could not be loaded: {file.name}.")
        if not snapshots:
            errors.append("No recorded public source snapshots are available.")
        opportunities = [item for snapshot in snapshots for item in parse_snapshot(snapshot)]
        _enrich_oist(opportunities, snapshots)
        return DiscoveryResult(
            query="recorded public source examples", opportunities=opportunities, snapshots=snapshots,
            errors=errors, provider="TinyFish (recorded public snapshots)", mode="cached",
        )
