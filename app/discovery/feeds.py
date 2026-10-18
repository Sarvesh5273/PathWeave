"""Public ATS feed normalization without provider calls or invented posting facts.

Scout behavioral reference: pipeline/feeds.ts. Inline descriptions retain the
original feed URL, requested URL and retrieval time, not a fictional posting fetch.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any

from .contracts import SourceLead, WebPage
from .urls import ATSRef, MAX_PAGE_CHARS, canonical_url, classify_url, detect_ats


MAX_FEED_ROWS = 1_000


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag == "br":
            self.parts.append("\n")
        if tag == "li":
            self.parts.append("\n- ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        if tag in {"p", "div", "li", "br", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def _text(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip() or len(value) > 5_000:
        return None
    parser = _Text()
    try:
        parser.feed(value)
    except (ValueError, RecursionError):
        return None
    text = " ".join("".join(parser.parts).split())[:500]
    # Feed rows are opening metadata, not public applicant/person records.
    if re.search(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", text, re.I):
        return None
    return text or None


def _json_body(page: WebPage) -> Any:
    if page.json_body is not None:
        return page.json_body
    text = page.snapshot.text.strip()
    if not text or len(text) > MAX_PAGE_CHARS:
        return None
    start = re.search(r"[\[{]", text)
    end = max(text.rfind("}"), text.rfind("]"))
    if start is None or end <= start.start():
        return None
    core = text[start.start():end + 1]
    # TinyFish can return markdown escapes or literal controls inside JSON strings.
    no_control = re.sub(r"[\x00-\x1f]+", " ", core)
    unescaped = re.sub(r'\\([^"\\/bfnrtu])', r"\1", no_control)
    for candidate in (core, no_control, unescaped):
        try:
            return json.loads(candidate)
        except (ValueError, RecursionError):
            continue
    return None


def _identifier(value: Any, pattern: str) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    value = str(value)
    return value if re.fullmatch(pattern, value, re.I) else None


def _description(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_PAGE_CHARS:
        return None
    parser = _Text()
    try:
        parser.feed(value)
    except (ValueError, RecursionError):
        return None
    text = re.sub(r"[ \t]+", " ", "".join(parser.parts))
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    if re.search(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", text, re.I):
        return None
    return text or None


def _date(value: Any) -> str | None:
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return datetime.fromtimestamp(value / 1000, timezone.utc).date().isoformat()
        if isinstance(value, str) and len(value) <= 100:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except (ValueError, OverflowError, OSError):
        pass
    return None


def _inline_page(page: WebPage, lead: SourceLead) -> WebPage:
    header = [f"# {lead.title}", "Evidence view: decoded public ATS feed row; original feed snapshot retained.", f"Organization: {lead.organization}"]
    if lead.location:
        header.append(f"Location: {lead.location}")
    if lead.employment_type:
        header.append(f"Employment type: {lead.employment_type}")
    if lead.posted_at:
        header.append(f"Posted: {lead.posted_at}")
    if lead.remote:
        header.append("Remote: yes")
    text = "\n".join(header) + "\n\n" + (lead.description or "")
    return WebPage(snapshot=page.snapshot.model_copy(update={
        "title": lead.title, "text": text,
        "content_hash": hashlib.sha256(text.encode()).hexdigest(),
    }), requested_url=page.requested_url, links=[lead.url])


def parse_feed(ref: ATSRef, page: WebPage) -> list[SourceLead] | None:
    """None means unsupported/unreadable feed; [] is a recognized empty feed.

    Redirects must remain on the requested board's exact public feed identity.
    Malformed/unsafe individual rows are skipped, preserving usable siblings.
    """
    if not ref.readable or not ref.feed_url:
        return None
    if len(page.snapshot.text) > MAX_PAGE_CHARS or re.search(
        r"(?:please (?:sign in|log in) to (?:view|access)|(?:login|sign in|log in) (?:is )?required to (?:view|access))",
        page.snapshot.text, re.I,
    ):
        return None
    source = canonical_url(page.snapshot.url)
    expected = canonical_url(ref.feed_url)
    if not expected or source != expected or canonical_url(page.requested_url) != expected:
        return None
    data = _json_body(page)
    if ref.ats == "lever":
        rows = data if isinstance(data, list) else None
    else:
        key = "content" if ref.ats == "smartrecruiters" else "jobs"
        rows = data.get(key) if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return None
    leads: list[SourceLead] = []
    seen: set[str] = set()
    for row in rows[:MAX_FEED_ROWS]:
        if not isinstance(row, dict):
            continue
        title = _text(row.get("text" if ref.ats == "lever" else "name" if ref.ats == "smartrecruiters" else "title"))
        if not title:
            continue
        url: str | None = None
        organization = ref.organization
        location = None
        description = employment_type = posted_at = None
        remote = None
        if ref.ats == "greenhouse":
            identifier = _identifier(row.get("id"), r"\d{1,30}")
            if identifier:
                url = f"{ref.board_url}/jobs/{identifier}"
            loc = row.get("location")
            location = _text(loc.get("name")) if isinstance(loc, dict) else None
            organization = _text(row.get("company_name")) or organization
            posted_at = _date(row.get("first_published")) or _date(row.get("updated_at"))
            remote = bool(re.search(r"remote", location, re.I)) if location else None
        elif ref.ats == "lever":
            url = row.get("hostedUrl") if isinstance(row.get("hostedUrl"), str) else None
            categories = row.get("categories")
            if isinstance(categories, dict):
                locations = categories.get("allLocations")
                if isinstance(locations, list):
                    location = "; ".join(item for value in locations[:20] if (item := _text(value)))[:500] or None
                location = location or _text(categories.get("location"))
                employment_type = _text(categories.get("commitment"))
            parts = [_description(row.get("descriptionPlain"))]
            for item in row.get("lists", [])[:40] if isinstance(row.get("lists"), list) else []:
                if isinstance(item, dict):
                    heading, content = _text(item.get("text")), _description(item.get("content"))
                    if content:
                        parts.append((f"## {heading}\n" if heading else "") + content)
            parts.append(_description(row.get("additionalPlain")))
            description = "\n\n".join(part for part in parts if part) or None
            if description and len(description) > MAX_PAGE_CHARS:
                description = None
            posted_at = _date(row.get("createdAt"))
            remote = True if row.get("workplaceType") == "remote" else None
        elif ref.ats == "smartrecruiters":
            identifier = _identifier(row.get("id"), r"\d{6,30}(?:-[a-z0-9_.-]+)?")
            if identifier:
                url = f"https://{ref.host}/{ref.org}/{identifier}"
            loc = row.get("location")
            if isinstance(loc, dict):
                location = _text(loc.get("fullLocation")) or ", ".join(
                    item for key in ("city", "country") if (item := _text(loc.get(key)))
                ) or None
            company = row.get("company")
            organization = (_text(company.get("name")) if isinstance(company, dict) else None) or organization
            posted_at = _date(row.get("releasedDate"))
            employment = row.get("typeOfEmployment")
            employment_type = _text(employment.get("label")) if isinstance(employment, dict) else None
            remote = loc.get("remote") if isinstance(loc, dict) and type(loc.get("remote")) is bool else None
        elif ref.ats == "workable":
            identifier = _identifier(row.get("shortcode"), r"[a-z0-9]{1,40}")
            if isinstance(row.get("url"), str):
                url = row["url"]
            elif identifier:
                url = f"{ref.board_url}/j/{identifier}"
            location = ", ".join(item for key in ("city", "country") if (item := _text(row.get(key)))) or None
            organization = _text(data.get("name")) or organization
            posted_at = _date(row.get("published_on")) or _date(row.get("created_at"))
            employment_type = _text(row.get("employment_type"))
            remote = row.get("telecommuting") if type(row.get("telecommuting")) is bool else None
        lead = classify_url(url) if url else None
        target = detect_ats(url) if url else None
        # Feed links must be actual openings on the same board, never redirects,
        # generic indexes, applicant URLs, or another employer's feed injection.
        unscoped_workable = bool(ref.ats == "workable" and target and target.ats == "workable" and not target.org
                                 and identifier and target.posting_id == identifier.upper())
        if ref.ats == "workable" and identifier and target and target.posting_id != identifier.upper():
            continue
        if not lead or lead.kind != "posting" or not target or (target.board_url != ref.board_url and not unscoped_workable) or lead.url in seen:
            continue
        seen.add(lead.url)
        lead = lead.model_copy(update={
            "title": title, "organization": organization, "location": location,
            "via": "feed", "source_url": source,
            "description": description, "employment_type": employment_type,
            "posted_at": posted_at, "remote": remote,
        })
        if description:
            lead.evidence_page = _inline_page(page, lead)
            lead.evidence_transform = "decoded_json_html_feed_row_with_title_scope"
        leads.append(lead)
    return leads
