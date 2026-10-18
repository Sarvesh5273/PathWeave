"""Bounded public source identities and leads, inspired by Scout's URL stages.

No networking is performed here. URL checks are not DNS/redirect verification:
the transport must still validate every redirect and public Fetch response.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Literal
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlsplit, urlunsplit

from app.sources import TinyFishError, _public_url

from .contracts import SourceLead, WebPage
from .search_plan import EXCLUDED_DOMAINS


MAX_PAGE_CHARS = 250_000
MAX_LINKS = 2_000
MAX_SOURCE_LEADS = 100
_SLUG = re.compile(r"[a-z0-9][a-z0-9_.-]{0,119}", re.I)
_UUID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", re.I)
_IDENTITY_PARAMS = frozenset({
    "gh_jid", "jobid", "job_id", "jid", "id", "jobreqid", "req", "reqid", "posting", "pid", "vacancy",
})
_PRIVATE_KEY = re.compile(
    r"token|secret|password|api[_-]?key|session|auth|invite|"
    r"^(?:e?mail|phone|name|first[_-]?name|last[_-]?name|address|applicant|candidate|user|"
    r"redirect(?:_uri|_url)?|return(?:to|_url)?|next|continue|dest(?:ination)?|target|url)$", re.I,
)
_PRIVATE_PATH = re.compile(
    r"/(?:login|log-in|signin|sign-in|sign_in|signup|sign-up|register|account|dashboard|"
    r"my-account|profiles?|candidates?|users?|oauth|sso)(?:[/.;]|$)", re.I,
)
_ASSET = re.compile(r"\.(?:png|jpe?g|gif|svg|webp|ico|css|js|zip|mp[34]|woff2?)(?:$|/)", re.I)
_JUNK = re.compile(r"/(?:privacy|cookies?|terms|legal|sitemap|accessibility|press|investors?)(?:[/.]|$)", re.I)
_HINT = re.compile(r"job|career|position|opening|vacanc|intern|program|fellow|opportunit|apply|recruit|student|graduate|research|summer|scholar", re.I)
_SUFFIXES = frozenset({
    "co.uk", "ac.uk", "org.uk", "gov.uk", "co.in", "ac.in", "edu.in", "res.in", "org.in", "gov.in",
    "com.au", "edu.au", "org.au", "co.jp", "ac.jp", "or.jp", "com.sg", "edu.sg", "gov.sg", "ac.kr",
    "co.kr", "edu.cn", "com.cn", "ac.il", "co.il", "ac.nz", "co.nz", "com.br", "edu.br", "ac.za",
    "co.za", "edu.hk", "com.hk", "edu.tw", "com.tw", "ac.at", "edu.my", "com.my", "edu.pk", "edu.sa",
})


@dataclass(frozen=True)
class ATSRef:
    ats: Literal["greenhouse", "lever", "smartrecruiters", "workable", "workday", "ashby"]
    org: str
    host: str
    board_url: str
    feed_url: str | None
    posting_url: str | None
    readable: bool
    organization: str
    posting_id: str | None = None


def _safe_url(raw: str) -> str | None:
    if not isinstance(raw, str) or re.search(r"[\x00-\x1f\x7f\\]", raw):
        return None
    try:
        safe = _public_url(raw)
        parsed = urlsplit(safe)
        host = (parsed.hostname or "").lower().rstrip(".")
        if any(host == domain or host.endswith("." + domain) for domain in EXCLUDED_DOMAINS):
            return None
        # Also reject browser-specific numeric/encoded hostname interpretations.
        if "%" in host:
            return None
        if re.fullmatch(r"(?:0x[0-9a-f]+|[0-9]+)(?:\.(?:0x[0-9a-f]+|[0-9]+))*", host, re.I):
            try:
                if not ipaddress.ip_address(host).is_global:
                    return None
            except ValueError:
                return None
        decoded = parsed.path
        for _ in range(3):
            decoded = unquote(decoded)
        if _PRIVATE_PATH.search(decoded) or re.search(r"[\x00-\x1f\x7f\\]", decoded) or "@" in decoded:
            return None
        # Check *before* dropping tracking parameters; never launder unsafe input.
        pairs = parse_qsl(parsed.query, keep_blank_values=True)
        fragment = urlsplit(raw.strip()).fragment
        if "=" in fragment:
            pairs += parse_qsl(fragment, keep_blank_values=True)
        for key, value in pairs:
            for _ in range(3):
                key, value = unquote(key), unquote(value)
            if (_PRIVATE_KEY.search(key) or "@" in value or re.search(r"(?:https?:)?//", value, re.I)
                    or re.search(r"[\x00-\x1f\x7f]", key + value)):
                return None
            if key.lower() in _IDENTITY_PARAMS and not _SLUG.fullmatch(value):
                return None
        return safe
    except (TinyFishError, ValueError, UnicodeError):
        return None


def _pretty_org(org: str) -> str:
    return " ".join(word.capitalize() for word in re.split(r"[-_\s]+", org.split("/")[0]) if word)


def _ats(safe: str) -> ATSRef | None:
    parsed = urlsplit(safe)
    host = (parsed.hostname or "").lower().rstrip(".").removeprefix("www.")
    parts = [part for part in parsed.path.split("/") if part]
    org = parts[0] if parts else ""
    posting_id = None
    if re.fullmatch(r"(?:job-)?boards(?:\.eu)?\.greenhouse\.io", host):
        if org == "embed":
            org = dict(parse_qsl(parsed.query)).get("for", "")
        if not _SLUG.fullmatch(org):
            return None
        org = org.lower()
        eu = ".eu." in host
        host = f"job-boards{'.eu' if eu else ''}.greenhouse.io"
        board = f"https://{host}/{org}"
        if len(parts) >= 3 and parts[1] == "jobs" and re.fullmatch(r"\d{1,30}", parts[2]):
            posting_id = parts[2]
        else:
            jid = dict(parse_qsl(parsed.query)).get("gh_jid")
            if jid and re.fullmatch(r"\d{1,30}", jid):
                posting_id = jid
        return ATSRef("greenhouse", org, host, board,
                      f"https://boards-api{'.eu' if eu else ''}.greenhouse.io/v1/boards/{org}/jobs",
                      f"{board}/jobs/{posting_id}" if posting_id else None, True, _pretty_org(org), posting_id)
    if host in {"jobs.lever.co", "jobs.eu.lever.co", "jobs.ashbyhq.com"}:
        is_ashby = host == "jobs.ashbyhq.com"
        decoded_org = unquote(org)
        if not _SLUG.fullmatch(decoded_org.replace(" ", "-")):
            return None
        if not is_ashby:
            org = org.lower()
        if len(parts) >= 2 and _UUID.fullmatch(parts[1]):
            posting_id = parts[1].lower()
        board = f"https://{host}/{org}"
        feed = None if is_ashby else f"https://api{'.eu' if '.eu.' in host else ''}.lever.co/v0/postings/{org}?mode=json"
        return ATSRef("ashby" if is_ashby else "lever", org, host, board, feed,
                      f"{board}/{posting_id}" if posting_id else None, not is_ashby, _pretty_org(decoded_org), posting_id)
    if host.endswith(".myworkdayjobs.com"):
        if parts and re.fullmatch(r"[a-z]{2}(?:-[a-z]{2})?", parts[0], re.I):
            parts = parts[1:]
        if not parts or not _SLUG.fullmatch(parts[0]):
            return None
        site = parts[0]
        org = f"{host.split('.')[0]}/{site}"
        if len(parts) >= 4 and parts[1] == "job" and _SLUG.fullmatch(parts[-1]):
            posting_id = parts[-1]
        return ATSRef("workday", org, host, f"https://{host}/{site}", None,
                      f"https://{host}/{'/'.join(parts)}" if posting_id else None, True, _pretty_org(org), posting_id)
    if host in {"jobs.smartrecruiters.com", "careers.smartrecruiters.com"}:
        if not _SLUG.fullmatch(org):
            return None
        if len(parts) >= 2 and re.fullmatch(r"\d{6,30}(?:-[a-z0-9_.-]+)?", parts[1], re.I):
            posting_id = parts[1].split("-", 1)[0]
        return ATSRef("smartrecruiters", org, "jobs.smartrecruiters.com",
                      f"https://careers.smartrecruiters.com/{org}",
                      f"https://api.smartrecruiters.com/v1/companies/{org}/postings?limit=100",
                      f"https://jobs.smartrecruiters.com/{org}/{parts[1]}" if posting_id else None,
                      True, _pretty_org(org), posting_id)
    if host == "apply.workable.com":
        # Organization-less public posting URLs inherit company identity only
        # from a validated feed; 'j' is not an employer board slug.
        if org.lower() == "j":
            if len(parts) in {2, 3} and (len(parts) == 2 or parts[2] == "apply") and re.fullmatch(r"[a-z0-9]{1,40}", parts[1], re.I):
                posting_id = parts[1].upper()
                return ATSRef("workable", "", host, f"https://{host}", None,
                              f"https://{host}/j/{posting_id}", True, "Unknown", posting_id)
            return None
        if org.lower() == "api" or not _SLUG.fullmatch(org):
            return None
        org = org.lower()
        if len(parts) >= 3 and parts[1] == "j" and re.fullmatch(r"[a-z0-9]{1,40}", parts[2], re.I):
            posting_id = parts[2].upper()
        board = f"https://{host}/{org}"
        return ATSRef("workable", org, host, board, f"https://{host}/api/v1/widget/accounts/{org}",
                      f"{board}/j/{posting_id}" if posting_id else None, True, _pretty_org(org), posting_id)
    return None


def detect_ats(raw: str) -> ATSRef | None:
    safe = _safe_url(raw)
    return _ats(safe) if safe else None


def canonical_url(raw: str) -> str | None:
    """Public identity without tracking; secret/login input is rejected, not cleaned."""
    safe = _safe_url(raw)
    if not safe:
        return None
    parsed = urlsplit(safe)
    ref = _ats(safe)
    if ref and ref.posting_url:
        return ref.posting_url
    if ref and (len([p for p in parsed.path.split("/") if p]) == 1 or "/embed" == parsed.path.rstrip("/")):
        return ref.board_url
    host = (parsed.hostname or "").lower().rstrip(".").removeprefix("www.")
    if ":" in host:
        host = f"[{host}]"
    path = parsed.path.rstrip("/") or "/"
    pairs = [(key.lower(), value) for key, value in parse_qsl(parsed.query) if key.lower() in _IDENTITY_PARAMS]
    if len({key for key, _ in pairs}) != len(pairs):
        return None
    # Public feed query semantics are not tracking (Lever requires mode=json).
    if host in {"api.lever.co", "api.eu.lever.co"} and path.startswith("/v0/postings/"):
        mode = dict(parse_qsl(parsed.query)).get("mode", "json")
        if mode != "json":
            return None
        pairs.append(("mode", "json"))
    if host == "api.smartrecruiters.com" and re.fullmatch(r"/v1/companies/[^/]+/postings", path):
        pairs.append(("limit", "100"))
    return urlunsplit(("https", host, path, urlencode(sorted(pairs)), ""))


def classify_url(raw: str) -> SourceLead | None:
    url = canonical_url(raw)
    if not url:
        return None
    path = urlsplit(url).path
    if _ASSET.search(path) or _JUNK.search(path):
        return None
    ref = detect_ats(raw)
    kind: Literal["posting", "board", "page"] = "page"
    if ref:
        kind = "posting" if ref.posting_url else "board"
        url = ref.posting_url or ref.board_url
    else:
        # Generic careers/search/category indexes remain pages, not openings.
        parts = [unquote(p) for p in path.split("/") if p]
        has_job_id = any(key in _IDENTITY_PARAMS for key, _ in parse_qsl(urlsplit(url).query))
        explicit_path = bool(re.search(r"/(?:jobs?|positions?|openings?|vacancies)/(?:[^/]+/)*[^/]*\d{3,}[^/]*$", path, re.I)
                             or re.search(r"/(?:jobs?|positions?|openings?|vacancies)/\d{3,}/[^/]+$",path,re.I))
        singular_slug = bool(re.search(r"/(?:job|position|opening)/[a-z0-9]+(?:-[a-z0-9]+){2,}$", path, re.I))
        if (has_job_id and _HINT.search(path)) or explicit_path or singular_slug:
            kind = "posting"
        if parts and (parts[-1].lower() in {"search", "all", "index", "index.html", "apply"}
                      or parts[-1].lower() in {"jobs", "careers"} and not has_job_id):
            kind = "page"
    return SourceLead(url=url, organization=ref.organization if ref else None, kind=kind, source_url=url)


def _base_domain(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    labels = host.split(".")
    count = 3 if ".".join(labels[-2:]) in _SUFFIXES else 2
    return ".".join(labels[-count:])


class _Anchors(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.href: str | None = None
        self.label: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag == "a" and not self.hidden:
            self.href = dict(attrs).get("href")
            self.label = []

    def handle_data(self, data: str) -> None:
        if self.href is not None and not self.hidden and sum(map(len, self.label)) < 500:
            self.label.append(data[:500])

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        if tag == "a" and self.href is not None:
            if len(self.links) < MAX_LINKS:
                self.links.append((self.href, " ".join("".join(self.label).split())[:500]))
            self.href = None
            self.label = []


def posting_links(page: WebPage) -> list[SourceLead]:
    """Known ATS and relevant same-site links, with final-page source attribution.

    Generic program pages and ATS boards may be leads; neither is falsely labelled
    an individual posting. Root applies its narrower per-board/run work budget.
    """
    source = canonical_url(page.snapshot.url)
    if not source or not canonical_url(page.requested_url) or len(page.snapshot.text) > MAX_PAGE_CHARS:
        return []
    if re.search(r"(?:please (?:sign in|log in) to (?:view|access)|(?:login|sign in|log in) (?:is )?required to (?:view|access))", page.snapshot.text, re.I):
        return []
    candidates = [(raw, "") for raw in page.links[:MAX_LINKS]]
    parser = _Anchors()
    try:
        parser.feed(page.snapshot.text)
        candidates.extend(parser.links)
    except (ValueError, RecursionError):
        pass
    candidates.extend((match[2], match[1]) for match in re.finditer(r"\[([^\]\n]{0,500})\]\(([^\s)]+)\)", page.snapshot.text))
    result: list[SourceLead] = []
    seen = {source}
    for raw, title in candidates[:MAX_LINKS]:
        if not isinstance(raw, str) or not raw or raw.startswith("#"):
            continue
        absolute = urljoin(page.snapshot.url, raw)
        lead = classify_url(absolute)
        if not lead or lead.url in seen:
            continue
        ref = detect_ats(absolute)
        if not ref and (_base_domain(lead.url) != _base_domain(source) or not _HINT.search(urlsplit(lead.url).path)):
            continue
        seen.add(lead.url)
        if ref and ref.ats == "workday" and ref.posting_id:
            parts = [unquote(p) for p in urlsplit(lead.url).path.split("/") if p]
            title = title or re.sub(r"_[A-Za-z]*-?\d[\w-]*$", "", parts[-1]).replace("-", " ").strip()
            lead.location = parts[parts.index("job") + 1].replace("-", " ")
        lead.title = " ".join(title.split())[:500]
        lead.via = "link"
        lead.source_url = source
        result.append(lead)
        if len(result) >= MAX_SOURCE_LEADS:
            break
    return sorted(result, key=lambda item: item.kind != "posting")
