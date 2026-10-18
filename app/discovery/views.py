"""Scout listing views over persisted hunt results; no invented postings or facts."""
from __future__ import annotations

from datetime import datetime, timezone

from .contracts import DiscoveryListing, DiscoveryPreferences
from .extract import deadline_details
from .filters import classify_constraints


def listing_view(listings: list[DiscoveryListing], *, view: str = "visible", sort: str = "match",
                 query: str = "", kind: str | None = None, visa: str | None = None,
                 funding: str | None = None, min_score: int = 0,
                 preferences: DiscoveryPreferences | None = None) -> list[DiscoveryListing]:
    preferences = preferences or DiscoveryPreferences(roles=["internship"])
    rows=[]
    for listing in listings:
        listing = classify_constraints(listing, preferences, funding=funding)
        if view=="saved":
            if not listing.saved:continue
        elif view=="hidden":
            if not listing.hidden:continue
        else:
            if listing.hidden or listing.call_status=="closed":continue
            if view=="new" and not listing.is_new:continue
            if view=="review":
                if listing.constraint_status!="needs_review":continue
            elif listing.constraint_status!="match":continue
        if kind and listing.kind!=kind:continue
        if visa=="sponsors" and listing.visa_status!="sponsors":continue
        if visa=="not_restricted" and listing.visa_status in {"not_sponsored","citizens_only"}:continue
        if listing.score<min_score:continue
        text=f"{listing.title} {listing.organization} {' '.join(listing.locations)}".casefold()
        if query.strip().casefold() not in text:continue
        rows.append(listing)
    def exact_deadline(listing):
        precision,value=deadline_details(listing.deadline_text)
        if precision!=listing.deadline_precision or precision not in {"exact","date"} or value is None:
            return float("inf")
        return datetime.combine(value,datetime.min.time(),tzinfo=timezone.utc).timestamp() if not isinstance(value,datetime) else value.timestamp()
    if sort=="deadline":rows.sort(key=lambda v:(exact_deadline(v),-v.score,v.id))
    elif sort=="newest":rows.sort(key=lambda v:(v.is_new,v.checked_at,v.score),reverse=True)
    else:rows.sort(key=lambda v:(-v.score,exact_deadline(v),v.id))
    return rows[:200]


def hunt_summary(listings: list[DiscoveryListing], events: list[dict], preferences: DiscoveryPreferences | None = None) -> dict:
    visible=listing_view(listings,preferences=preferences)
    return {"total":len(visible),"new":sum(v.is_new for v in visible),"saved":sum(v.saved for v in listings),
            "needs_review":len(listing_view(listings,view="review",preferences=preferences)),
            "hidden":sum(v.hidden for v in listings),"organizations":len({v.organization for v in visible}),
            "sources":len({e.get('url') for e in events if e.get('url') and e.get('stage') in {'fetch','feed','agent'}}),
            "by_kind":{kind:sum(v.kind==kind for v in visible) for kind in ('job','program')},
            "by_visa":{status:sum(v.visa_status==status for v in visible) for status in ('sponsors','not_sponsored','citizens_only','unknown')},
            "by_funding":{status:sum(v.funding_level==status for v in visible) for status in ('fully_funded','paid','unpaid','unknown')}}
