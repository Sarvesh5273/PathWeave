"""Explicit search conditions, supported by posting text rather than ranking scores.

No LLM, network, applicant eligibility decision or inferred missing benefit. Exact
excerpts stay attached to the source observation. Unknowns are a separate review view.
"""
from __future__ import annotations

import re

from .contracts import DiscoveryListing, DiscoveryPreferences, WebPage
from .ranking import place_matches

COMPONENTS = {
    "stipend": r"\b(?:stipend|salary|living (?:allowance|support|expenses|costs)|subsistence allowance|monthly subsidy)\b",
    "housing": r"\b(?:accommodation|housing|lodging)\b",
    "round_trip_travel": r"\b(?:round[ -]trip|return)\s+(?:airfares?|flights?|air tickets?|travel|transportation)\b|\b(?:airfares?|flights?|travel)\s+(?:to and from|both ways)\b",
}
NEGATIVE = re.compile(r"\b(?:not covered|not provided|not included|no reimbursement|not reimbursed|own expense|at your expense|self[ -]funded|must pay|does not cover|will not cover|not available|not paid|unpaid|for a fee|additional (?:fee|cost)|paid by (?:you|interns?|students?|participants?)|no (?:stipend|salary|housing|accommodation|travel|return|round[ -]trip))\b", re.I)
POSITIVE = re.compile(r"\b(?:provided|provide|covered|cover|paid|funded|reimburse\w*|included|includes|receive|receives|free)\b|\b\d[\d,.]*\s*(?:JPY|USD|EUR|CHF|INR|yen|dollars?|euros?)\b", re.I)
UNCERTAIN = re.compile(r"\b(?:may|might|possibly|potentially|subject to (?:approval|availability)|depending on|only (?:for|if)|available to eligible|if (?:eligible|selected|approved)|can apply for|help (?:you )?(?:find|locate)|assist (?:you )?(?:in|with) finding)\b", re.I)
BENEFIT_HEADING = re.compile(r"\b(?:be provided with|we provide|covered costs|what we cover|support includes|we cover)\b", re.I)


def _clauses(text: str):
    in_benefits = False
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            # Nested headings inherit a benefits heading; a new top-level section
            # closes it. Never treat all mentions of costs as promised benefits.
            if line.startswith("# "):
                in_benefits = bool(BENEFIT_HEADING.search(line))
            elif BENEFIT_HEADING.search(line):
                in_benefits = True
            elif re.search(r"\b(?:access to|eligibility|expenses|fees|costs|not covered|exclusions|how to apply)\b",line,re.I):
                in_benefits = False
        if BENEFIT_HEADING.search(line) and re.fullmatch(r"\s*(?:#{1,6}\s*)?(?:be provided with|we provide|covered costs|what we cover|support includes|we cover)\s*:?\s*", line, re.I):
            in_benefits = True
        for part in re.split(r"(?<=[.!?;])\s+(?=[A-Z*])", line):
            quote = part.strip()
            if quote:
                yield quote, in_benefits and len(quote) < 100 and not re.search(r"\b(?:research|study|market|project|experience|workshops?|help|find|cost)\b",quote,re.I)


def source_filter_evidence(listing: DiscoveryListing, page: WebPage | None) -> DiscoveryListing:
    """Use the selected-posting scope; never turn search snippets into proof."""
    if page is None or listing.verification == "uncertain":
        return listing
    from .bridge import _scope
    from .urls import canonical_url
    if canonical_url(listing.source_url) not in {canonical_url(page.snapshot.url), canonical_url(page.requested_url)}:
        return listing.model_copy(update={"filter_evidence": {}, "stipend": None, "housing": None,
                                          "round_trip_travel": None, "funding_level": "unknown"})
    text = _scope(listing, page)
    if not text:
        return listing.model_copy(update={"filter_evidence": {}, "stipend": None, "housing": None,
            "round_trip_travel": None, "travel": None, "funding_level": "unknown", "funding_note": None})
    evidence: dict[str, list[str]] = {}
    location_quotes = []
    for line in text.splitlines():
        if not line.strip():
            continue
        is_heading = line.lstrip().startswith("#") and listing.title.casefold() in line.casefold()
        location_label = bool(re.match(r"\s*(?:#{1,5}\s*)?(?:location|locations|place|based in)\s*[:\-]", line, re.I))
        role_place = bool(re.search(r"\b(?:on[ -]site|internship|this (?:role|position)|you(?:'ll| will) work|based)\b.{0,180}\b(?:in|at our headquarters in)\b", line, re.I))
        if (is_heading or location_label or role_place) and not re.search(r"\b(?:offices also|our offices|privacy|example|remote worldwide|interested in|career in|may|might)\b", line, re.I):
            if any(place_matches(place, line) for place in listing.locations):
                location_quotes.append(line.strip()[:1200])
    if location_quotes:
        evidence["location"] = location_quotes[:6]
    clauses = list(_clauses(text))
    values = {}
    for component, pattern in COMPONENTS.items():
        positive, negative, uncertain = [], [], []
        for quote, benefits in clauses:
            if not re.search(pattern, quote, re.I):
                continue
            if re.search(r"\b(?:research|market|project|study|experience|workshop|you pay|applicants pay|participants pay|students pay|interns pay)\b",quote,re.I):
                if not re.search(r"\b(?:interns?|participants?|students?|you) (?:receive|are provided|will receive)\b",quote,re.I):
                    continue
            if UNCERTAIN.search(quote):
                uncertain.append(quote)
            elif NEGATIVE.search(quote):
                # "Unpaid" does not negate a separately stated living subsidy.
                if component == "stipend" and re.search(r"\bunpaid\b",quote,re.I) and re.search(r"subsidy|stipend|allowance", quote, re.I) and re.search(r"provide|provided|receive|monthly", quote, re.I) and not re.search(r"\bnot\b|\bno (?:salary|stipend|allowance|subsidy)",quote,re.I):
                    positive.append(quote)
                else:
                    negative.append(quote)
            elif POSITIVE.search(quote) or benefits:
                positive.append(quote)
        values[component] = None if uncertain or (positive and negative) else True if positive else False if negative else None
        if positive or negative or uncertain:
            evidence[component] = list(dict.fromkeys([*positive, *negative, *uncertain]))[:6]
    stipend, housing, trip = (values[k] for k in COMPONENTS)
    level = "fully_funded" if stipend is True and housing is True and trip is True else "paid" if stipend is True else "unpaid" if stipend is False else "unknown"
    quotes = list(dict.fromkeys(q for key, parts in evidence.items() if key != "location" for q in parts))
    return listing.model_copy(update={"filter_evidence": evidence, "stipend": stipend, "housing": housing,
        "round_trip_travel": trip, "travel": trip, "funding_level": level,
        "funding_note": " | ".join(quotes)[:1200] or None})


def classify_constraints(listing: DiscoveryListing, preferences: DiscoveryPreferences,
                         *, funding: str | None = None) -> DiscoveryListing:
    reasons, unknown, excluded = [], False, False
    if listing.verification == "uncertain":
        unknown = True
        reasons.append("Posting has not been verified by a current source observation.")
    if preferences.locations:
        proof = listing.filter_evidence.get("location", []) if listing.verification != "uncertain" else []
        matched = any(place_matches(wanted, label) and any(place_matches(wanted, quote) for quote in proof)
                      for wanted in preferences.locations for label in listing.locations)
        if matched:
            reasons.append("Location supported by the retrieved posting: " + ", ".join(listing.locations))
        elif proof and listing.locations:
            reasons.append("Posting location is outside your selected places.")
            excluded = True
        else:
            reasons.append("Selected location is not confirmed by posting evidence.")
            unknown = True
    selected = "fully_funded" if "fully_funded" in {preferences.funding, funding} else "paid" if "paid" in {preferences.funding, funding} else "any"
    if selected != "any":
        required = ("stipend", "housing", "round_trip_travel") if selected == "fully_funded" else ("stipend",)
        for key in required:
            value = getattr(listing, key)
            proof = listing.filter_evidence.get(key, []) if listing.verification != "uncertain" else []
            label = {"stipend": "Stipend/living support", "housing": "Accommodation", "round_trip_travel": "Round-trip travel"}[key]
            if value is True and proof:
                reasons.append(label + " stated in the source.")
            elif value is False and proof:
                excluded = True
                reasons.append(label + " is explicitly not covered.")
            else:
                unknown = True
                reasons.append(label + " coverage is unconfirmed.")
    if preferences.needs_visa_sponsorship:
        if listing.visa_status in {"not_sponsored", "citizens_only"}:
            excluded = True
            reasons.append("Visa/work-right conditions do not match the sponsorship request.")
        elif listing.visa_status != "sponsors":
            unknown = True
            reasons.append("Visa sponsorship is unconfirmed.")
    if listing.funding_level == "fully_funded":
        reasons.append("All three funding components are stated; verify payment amounts, eligibility, caps, upfront costs and fees at the source.")
    status = "excluded" if excluded else "needs_review" if unknown else "match"
    return listing.model_copy(update={"constraint_status": status, "constraint_reasons": reasons})


def hydrate_filter_evidence(listings: list[DiscoveryListing], pages: list[WebPage]) -> list[DiscoveryListing]:
    """Re-evaluate existing hunt observations under current filtering rules, no Fetch."""
    from .urls import canonical_url
    result=[]
    for listing in listings:
        choices=[p for p in pages if canonical_url(listing.source_url) in
                 {canonical_url(p.snapshot.url), canonical_url(p.requested_url)}]
        normalize=lambda value:" ".join(value.casefold().split())
        page=max(choices,key=lambda p:(normalize(p.snapshot.title).startswith(normalize(listing.title)),
                                      p.snapshot.checked_at)) if choices else None
        if page is None or listing.verification=="uncertain":
            result.append(listing.model_copy(update={"filter_evidence":{}}))
        else:
            result.append(source_filter_evidence(listing,page))
    return result
