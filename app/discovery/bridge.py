"""Selected discovery labels -> source-bound preparation, without readiness claims."""

from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime

from app.models import Fact, Opportunity
from app.sources import SHARED_FIELDS, _date_from_fragment, parse_snapshot

from .contracts import DiscoveryListing, WebPage
from .urls import canonical_url


_LIST_FIELDS = {
    "documents", "skills", "preferred_skills", "technical_skills", "preferred_technical_skills", "programming_languages",
    "preferred_programming_languages", "cs_topics", "preferred_cs_topics", "tools", "preferred_tools",
    "degree_levels", "fields", "research_areas", "research_interests",
}
_ALIASES = {
    "cv": ("cv", "curriculum vitae", "resume", "résumé"),
    "statement": ("statement", "motivation letter", "letter of motivation"),
    "transcript": ("transcript", "academic records"),
    "reference": ("reference", "recommendation"),
    "identity_document": ("identity document", "passport", "identification document"),
    "id_photo": ("id photo", "identification photo"),
    "diploma_or_enrollment": ("diploma", "enrollment certificate", "certificate of enrollment"),
    "bachelor": ("bachelor", "undergraduate"), "master": ("master", "graduate"),
    "complexity": ("complexity", "complexity analysis"),
    "algorithms": ("algorithms", "algorithm"),
    "cpp": ("c++", "cpp"),
    "computer_science": ("computer science", "cs"),
    "machine_learning": ("machine learning", "ml"),
    "artificial_intelligence": ("artificial intelligence", "ai"),
    "general_purpose_programming": ("general purpose programming", "general-purpose programming"),
}
_INSTRUCTION = re.compile(r"ignore (?:all |any |previous |prior |the )*(?:instructions|prompts|rules)|"
                          r"(?:system|developer|assistant)\s*(?:message|prompt|:)|"
                          r"(?:return|output|emit|respond with)\s+(?:only\s+)?(?:json|a json)", re.I)


def _text(value: str) -> str:
    return re.sub(r"[^\w+#]+", " ", value.casefold()).strip()


def _mentioned(value: str, excerpt: str) -> bool:
    # Token boundaries distinguish C from C++, Java from JavaScript, etc.
    candidates = _ALIASES.get(value.casefold(), (value,))
    haystack = " " + _text(excerpt) + " "
    return any(" " + _text(candidate.replace("_", " ")) + " " in haystack for candidate in candidates)


def _source_quote(excerpt: str, scope: str) -> bool:
    if not excerpt.strip() or excerpt not in scope or _INSTRUCTION.search(excerpt):
        return False
    start = scope.index(excerpt)
    left = scope.rfind("\n", 0, start) + 1
    right = scope.find("\n", start + len(excerpt))
    return not _INSTRUCTION.search(scope[left:right if right >= 0 else len(scope)])


def _headings(text: str) -> list[tuple[int, int, str]]:
    return [(m.start(), len(m[1]), re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", m[2]))
            for m in re.finditer(r"(?m)^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", text)]


def _section(text: str, headings: list[tuple[int, int, str]], index: int) -> str:
    start, level, _ = headings[index]
    end = next((position for position, depth, _ in headings[index + 1:] if depth <= level), len(text))
    return text[start:end]


def _cohort_labels(text: str) -> set[str]:
    labels=set()
    for line in text.splitlines():
        # A graduation limit is a qualification of this posting, not another intake.
        if re.search(r'\b(?:graduate|graduating|graduation|degree completion)\b',line,re.I):continue
        labels.update(_text(m[0]) for m in re.finditer(r'\b(?:Spring|Summer|Fall|Autumn|Winter)\s+20\d{2}\b',line,re.I))
    return labels


def _scope(listing: DiscoveryListing, page: WebPage) -> str:
    """A board quote must belong to the selected title, not merely exist on the page.

    Unstructured multi-listing pages need their individual posting fetched first.
    Markdown sections allow a conservative offline bridge for clearly scoped boards.
    """
    text = page.snapshot.text
    headings = _headings(text)
    matches = [i for i, (_, _, title) in enumerate(headings) if _text(title) == _text(listing.title)]
    if len(matches) == 1:
        selected = matches[0]
        dedicated = canonical_url(listing.apply_url) in {canonical_url(page.snapshot.url), canonical_url(page.requested_url)}
        title_matches = _text(page.snapshot.title).startswith(_text(listing.title))
        # A dedicated posting may use level-one headings for Description,
        # Qualifications and How to Apply. Those belong to the same opening.
        # Stop at a different opening, related-jobs section or cohort boundary.
        sibling_openings = [position for position, level, title in headings[selected+1:]
                            if level <= headings[selected][1]
                            and re.search(r"\b(?:intern(?:ship)?|fellowship|research (?:program|programme))\b", title, re.I)
                            and not re.match(r"(?:meet\b|internship (?:schedule|flow|details|benefits)|research (?:details|methods))",title,re.I)]
        if dedicated and title_matches and not page.json_body:
            text = text[headings[selected][0]:min(sibling_openings) if sibling_openings else len(text)]
        else:
            text = _section(text, headings, selected)
    elif canonical_url(listing.apply_url) not in {canonical_url(page.snapshot.url), canonical_url(page.requested_url)}:
        return ""
    elif len(matches) > 1:
        return ""
    # A selected named cohort must not inherit a different cohort's section.
    headings = _headings(text)
    cohort_headings = [i for i, (_, _, title) in enumerate(headings) if re.search(r"\b20\d{2}\b", title)]
    cycle = _text(listing.cycle)
    if cycle == "unknown" and len(cohort_headings) > 1:
        return ""
    if cycle != "unknown" and cohort_headings:
        matching = [i for i in cohort_headings if cycle in _text(headings[i][2])]
        if len(matching) == 1:
            # A dedicated posting's dated title identifies its cohort. Its
            # Description/Qualifications sections may be siblings of that title.
            # Preserve the already bounded posting instead of stopping at the
            # first company-description heading.
            dated_title = (len(cohort_headings) == 1 and
                           _text(headings[matching[0]][2]) == _text(listing.title) and
                           canonical_url(listing.apply_url) in {canonical_url(page.snapshot.url), canonical_url(page.requested_url)} and
                           _text(page.snapshot.title).startswith(_text(listing.title)) and not page.json_body)
            if not dated_title:
                text = _section(text, headings, matching[0])
        else:
            return ""
    cohort_labels = _cohort_labels(text)
    # A specifically titled posting can describe optional seasonal start dates
    # without defining independent cohort requirements. Common qualifications in
    # that posting remain usable; separate round headings stay scope boundaries.
    optional_seasons = bool(
        cycle != "unknown" and len(cohort_headings) == 1
        and cycle in _text(headings[cohort_headings[0]][2])
        and re.search(r"additional openings|other seasonal start dates?", text, re.I)
    )
    if (len(cohort_labels) > 1 and not optional_seasons) or (cohort_labels and cycle not in {"unknown", *cohort_labels}):
        return ""
    # Related jobs are not requirements of this posting, even on a dedicated page.
    for position, _, title in _headings(text):
        if re.match(r"(?:related|other|similar|recommended)\s+(?:jobs|roles|opportunities|positions)", title, re.I):
            return text[:position]
    return text


def _supported_value(fact: Fact) -> bool:
    value = fact.value
    if fact.name == "documents" and value == []:
        return bool(re.search(r"no\s+(?:application\s+)?documents?\s+(?:(?:are|is)\s+)?required", fact.excerpt, re.I))
    if fact.name in _LIST_FIELDS:
        if fact.kind == "requirement" and re.search(
            r"\b(?:not\s+(?:required|needed|allowed|accepted|considered)|"
            r"no .{0,40}(?:required|needed|allowed|accepted|considered)|do not|must not|forbidden)\b",
            fact.excerpt, re.I,
        ):
            return False
        return (isinstance(value, list) and bool(value) and len(value) <= 24
                and all(isinstance(item, str) and 0 < len(item.strip()) <= 120
                        and _mentioned(item, fact.excerpt) for item in value))
    if fact.name == "application_deadline":
        if not isinstance(value, str):
            return False
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return False
        if timestamp.tzinfo is None:
            return False
        parsed = _date_from_fragment(fact.excerpt)
        return value in fact.excerpt or (parsed is not None and parsed == timestamp)
    if fact.name == "portal_status":
        if not isinstance(value, str) or value not in {"open", "closed", "future"}:
            return False
        if value == "future":
            return bool(re.search(r"applications?\s+(?:will\s+)?open\s+(?:on|in|from)", fact.excerpt, re.I))
        if value == "open" and re.search(r"\bopen\s+(?:on|in|from|soon)\b", fact.excerpt, re.I):
            return False
        return bool(re.search(rf"(?:applications?|portal|role|job)\s+(?:(?:is|are)\s+)?(?:now\s+)?{value}\b", fact.excerpt, re.I))
    if fact.name == "portfolio":
        if "portfolio" not in fact.excerpt.casefold():
            return False
        if isinstance(value, bool):
            negative = bool(re.search(r"\b(?:no portfolio|portfolio.{0,20}not required|do not.{0,20}portfolio)\b", fact.excerpt, re.I))
            return negative if value is False else not negative and bool(re.search(r"\b(?:provide|submit|required|must|yes)\b", fact.excerpt, re.I))
        if isinstance(value, str):
            return bool(value.strip()) and _mentioned(value, fact.excerpt)
        return isinstance(value, list) and bool(value) and all(isinstance(item, str) and _mentioned(item, fact.excerpt) for item in value)
    if isinstance(value, str):
        return bool(value.strip()) and _mentioned(value, fact.excerpt)
    if isinstance(value, list):
        return bool(value) and all(isinstance(item, str) and _mentioned(item, fact.excerpt) for item in value)
    if isinstance(value, bool):
        # Canonical policy booleans need affirmative semantics, not a stray
        # 'no' elsewhere in a quote that could reverse a forbidden-document rule.
        if fact.name == "reference_forbidden":
            forbidden = bool(re.search(r"no .{0,40}(?:references?|recommendations?).{0,30}(?:allowed|accepted|considered)|"
                                       r"(?:references?|recommendations?).{0,40}(?:not allowed|forbidden)|do not.{0,30}(?:references?|recommendations?)", fact.excerpt, re.I))
            permitted = bool(re.search(r"(?:references?|recommendations?).{0,30}(?:are allowed|are accepted|are permitted)", fact.excerpt, re.I))
            return forbidden if value is True else permitted and not forbidden
        return bool(re.search(r"\b(?:true|yes)\b" if value else r"\b(?:false|no)\b", fact.excerpt, re.I))
    if isinstance(value, (int, float)) and math.isfinite(value):
        number_words = {0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}
        return _mentioned(f"{value:g}", fact.excerpt) or (value in number_words and _mentioned(number_words[value], fact.excerpt))
    # A supplied arbitrary object is not a validated typed policy.
    return False


def _validated_facts(listing: DiscoveryListing, page: WebPage | None) -> list[Fact]:
    source = canonical_url(listing.source_url)
    associated = bool(page and source in {canonical_url(page.snapshot.url), canonical_url(page.requested_url)})
    scope = _scope(listing, page) if associated else ""
    result = {name: Fact(name=name, kind=kind, source_url=listing.source_url,
                         source_id=page.snapshot.id if associated else "")
              for name, kind in SHARED_FIELDS.items()}
    seen: set[str] = set()
    kinds = {fact.name: {f.kind for f in listing.requirements if f.name == fact.name}
             for fact in listing.requirements}
    for original in listing.requirements:
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", original.name) or original.name == "requirement_set":
            raise ValueError("Discovery requirements need canonical, nonreserved fact names.")
        fact = original.model_copy(deep=True)
        if fact.kind == "preference" and "requirement" in kinds[fact.name]:
            fact.name = "preferred_" + fact.name
            if len(fact.name) > 80:
                raise ValueError("Scoped preference fact name exceeds the graph boundary.")
        fact.version_id = ""  # Only graph storage assigns semantic versions.
        evidence_url = canonical_url(fact.source_url)
        valid = bool(associated and _source_quote(fact.excerpt, scope)
                     and evidence_url in {source, canonical_url(page.snapshot.url)}
                     and (not fact.source_id or fact.source_id == page.snapshot.id)
                      and ((fact.status == "conflicting" and fact.value is None) or _supported_value(fact)))
        excerpt_cycles=_cohort_labels(fact.excerpt)
        if listing.cycle != "unknown" and any(cycle != _text(listing.cycle) for cycle in excerpt_cycles):
            valid=False  # Optional other-season wording is not this cohort's policy.
        if not valid:
            fact.status, fact.value, fact.excerpt = "unknown", None, ""
        if associated:
            fact.source_url, fact.source_id = page.snapshot.url, page.snapshot.id
            fact.simulated = page.snapshot.mode == "synthetic"
        else:
            fact.source_url, fact.source_id, fact.simulated = listing.source_url, "", False
        if fact.name in seen:
            previous = result[fact.name]
            if (previous.status == fact.status == "known" and previous.kind == fact.kind
                    and fact.name in _LIST_FIELDS and isinstance(previous.value, list) and isinstance(fact.value, list)):
                # Complementary atomic list observations are additive, not a
                # contradiction. Their combined evidence remains a real span.
                start = min(scope.index(previous.excerpt), scope.index(fact.excerpt))
                end = max(scope.index(previous.excerpt) + len(previous.excerpt), scope.index(fact.excerpt) + len(fact.excerpt))
                fact.excerpt = scope[start:end]
                fact.value = list(dict.fromkeys(previous.value + fact.value))
            elif (previous.status, previous.kind, previous.value) != (fact.status, fact.kind, fact.value):
                if previous.excerpt and fact.excerpt:
                    start = min(scope.index(previous.excerpt), scope.index(fact.excerpt))
                    end = max(scope.index(previous.excerpt) + len(previous.excerpt), scope.index(fact.excerpt) + len(fact.excerpt))
                    fact.excerpt = scope[start:end]
                    fact.status = "conflicting"
                else:
                    fact.status, fact.excerpt = "unknown", ""
                fact.value = None
                if previous.kind == "requirement":
                    fact.kind = "requirement"
        result[fact.name] = fact
        seen.add(fact.name)
    if len(result) > 64:
        raise ValueError("Selected discovery listing exceeds the graph's 64-fact boundary.")
    return list(result.values())


def review_listing_requirements(listing: DiscoveryListing, page: WebPage) -> DiscoveryListing:
    """Revalidate supplied facts before caching, displaying or selecting them.

    The bridge adds unknown shared fields for planning; discovery retains only the
    supplied observations. Required/preferred facts with the same name are scoped
    exactly as they will be in FalkorDB.
    """
    names = {f.name for f in listing.requirements}
    required = {f.name for f in listing.requirements if f.kind == "requirement"}
    names.update("preferred_" + f.name for f in listing.requirements
                 if f.kind == "preference" and f.name in required)
    try:
        facts = [f for f in _validated_facts(listing, page) if f.name in names]
    except ValueError:
        facts = []
    complete = (listing.enrichment_status in {"complete", "cached"} and bool(facts)
                and all(f.status == "known" and f.excerpt for f in facts))
    if listing.requirements and not complete and not any(f.name == "requirements_review" for f in facts):
        facts.append(Fact(name="requirements_review", kind="requirement", status="unknown",
                          source_url=page.snapshot.url, source_id=page.snapshot.id))
    return listing.model_copy(update={"requirements": facts,
        "enrichment_status": "complete" if complete else "partial" if listing.requirements else "pending"})


def _adapter_selection(listing: DiscoveryListing, page: WebPage) -> list[Opportunity]:
    parsed = [op for op in parse_snapshot(page.snapshot) if not op.id.startswith("source-")]
    if not parsed:
        return []
    # Supported parsers are authoritative; AI extraction cannot replace their
    # program-specific exceptions or spread one listing's facts to other rounds.
    title = _text(listing.title + " " + listing.organization)
    keys = {
        "Summer@EPFL": ("summer",),
        "OIST Research Internship": ("research", "internship"),
        "Mitacs Globalink Research Internship": ("globalink",),
        "Google Forward Deployed Engineer Intern": ("forward deployed engineer", "intern"),
    }
    parsed = [op for op in parsed if all(key in title for key in keys.get(op.program, (op.program.casefold(),)))]
    if listing.cycle.casefold().strip() != "unknown":
        candidates = [op for op in parsed if _text(op.cycle) == _text(listing.cycle)
                      or (re.fullmatch(r"20\d{2}", listing.cycle.strip())
                          and re.search(rf"\b{re.escape(listing.cycle.strip())}\b", op.cycle))]
        parsed = candidates if len(candidates) == 1 else []
    elif len(parsed) != 1:
        return []  # Ambiguous round: fetch/identify it before certification.
    return parsed


def listing_to_opportunities(listing: DiscoveryListing, page: WebPage | None) -> list[Opportunity]:
    """Bridge only the selected target; discovery metadata stays visibly separate.

    Missing snapshots, approximate dates and unsupported source shapes keep explicit
    unknowns. This performs no fetch, graph write, or competence assessment.
    """
    apply_url, source_url = canonical_url(listing.apply_url), canonical_url(listing.source_url)
    if not apply_url or not source_url:
        raise ValueError("Selected listings require public application and source URLs.")
    associated = bool(page and source_url in {canonical_url(page.snapshot.url), canonical_url(page.requested_url)})
    if associated:
        adapted = _adapter_selection(listing, page)
        if adapted:
            for opportunity in adapted:
                opportunity.discovery = listing.model_dump(mode="json")
                if listing.verification == "uncertain":
                    opportunity.verification = "uncertain"
            return adapted
    # A known source with a different/ambiguous cohort cannot be repurposed as a
    # generic opportunity carrying another call's requirements.
    mismatched_adapter = bool(associated and any(not op.id.startswith("source-") for op in parse_snapshot(page.snapshot)))
    facts = _validated_facts(listing, None if mismatched_adapter else page)
    by_name = {fact.name: fact for fact in facts}
    portal = by_name["portal_status"]
    verified = all(by_name[name].status == "known" for name in ("documents", "portal_status", "application_deadline"))
    uncertainty = (not associated or listing.verification == "uncertain"
                   or any(f.status == "conflicting" for f in facts))
    # Apply URL identifies individual postings on a shared page. Explicit cohort
    # identity additionally distinguishes repeat calls using the same application URL.
    identity = apply_url + "\n" + _text(listing.cycle)
    opportunity = Opportunity(
        id="listing-" + hashlib.sha256(identity.encode()).hexdigest()[:24],
        program=listing.title, cycle=listing.cycle,
        category="Company" if listing.kind == "job" else "Research",
        country="Unknown", source_url=page.snapshot.url if associated else source_url,
        checked_at=page.snapshot.checked_at if associated else listing.checked_at,
        call_status=portal.value if portal.status == "known" else "unknown",
        verification="uncertain" if uncertainty else "verified" if verified else "partial",
        mode=page.snapshot.mode if associated else "live", facts=facts,
        summary=listing.summary, discovery=listing.model_dump(mode="json"),
    )
    return [opportunity]
