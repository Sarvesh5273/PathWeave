"""New Python implementation of Scout's preference-driven search planning.

Behavior reference: Scout commit 0fbad8cc, pipeline/plan.ts and pipeline/urls.ts.
Only query planning is implemented here; no network, AI, scheduling or DB writes.
Dates in queries are search hints and must never be ingested as source facts.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from .contracts import DiscoveryPreferences, SearchTask


ATS_SEARCH_DOMAINS = (
    "job-boards.greenhouse.io", "boards.greenhouse.io", "jobs.lever.co",
    "myworkdayjobs.com", "jobs.smartrecruiters.com", "apply.workable.com",
)
EXCLUDED_DOMAINS = (
    "linkedin.com", "indeed.com", "glassdoor.com", "glassdoor.co.in",
    "ziprecruiter.com", "monster.com", "simplyhired.com", "facebook.com",
    "instagram.com", "twitter.com", "x.com", "youtube.com", "reddit.com",
    "quora.com", "pinterest.com", "tiktok.com", "levels.fyi", "teamblind.com",
)
LEVEL_WORDS = {"internship": "intern", "new_grad": "new grad", "entry_level": "entry level", "experienced": ""}
ROLE_NOISE = re.compile(
    r"\b(?:intern|interns|internship|internships|new grad|graduate|junior|senior|"
    r"entry[- ]level|role|position|engineer|developer|scientist|analyst|researcher|associate)\b",
    re.I,
)
LEVEL_PATTERNS = {
    "intern": re.compile(r"\bintern(?:s|ship|ships)?\b", re.I),
    "new grad": re.compile(r"\b(?:new grad|graduate)\b", re.I),
    "entry level": re.compile(r"\b(?:entry[- ]level|junior)\b", re.I),
}


def _join(*parts: str) -> str:
    return " ".join(" ".join(part.split()) for part in parts if part.strip())


def field_of(role: str) -> str:
    cleaned = re.sub(r"[,;/|]+", " ", ROLE_NOISE.sub(" ", role))
    return " ".join(cleaned.split()).lower() or role.lower()


def target_year(now: datetime | None = None) -> int:
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        raise ValueError("Search planning requires a timezone-aware clock.")
    clock = clock.astimezone(timezone.utc)
    return clock.year + int(clock.month >= 7)


def _role_with_level(role: str, level: str, word: str | None = None) -> str:
    pattern = LEVEL_PATTERNS.get(level)
    return role if pattern and pattern.search(role) else _join(role, level if word is None else word)


def plan_searches(preferences: DiscoveryPreferences, now: datetime | None = None) -> list[SearchTask]:
    """Prioritize named companies, primary searches, then broader secondary searches.

    As in Scout, the orchestrator must trim this complete plan to its run budget.
    Preserve research/company choices, visa queries, keywords, citizenship and places.
    Ashby is intentionally absent from ATS search hosts, not from the Agent pipeline.
    """
    p = preferences
    level = next((word for key, word in LEVEL_WORDS.items() if key in p.seniority), "")
    year = str(target_year(now))
    roles, places = p.roles[:3], p.locations[:3]
    first_place = places[0] if places else "remote" if p.remote_ok else ""
    primary: list[SearchTask] = []
    secondary: list[SearchTask] = []
    company_tasks = [SearchTask(
        intent="company", company=company, label=company,
        query=_join(company, "careers", _role_with_level(roles[0], level)),
        purpose=_join("Find the official careers page or job board of", company, "listing", level, "openings"),
        exclude_domains=EXCLUDED_DOMAINS,
    ) for company in p.companies]

    if "company_roles" in p.opportunity_types:
        ats_tasks = [SearchTask(
            intent="ats", label="job boards",
            query=_join(_role_with_level(role, level), places[i % len(places)] if places else first_place),
            purpose="Find individual open job and internship postings that match a student's search",
            include_domains=ATS_SEARCH_DOMAINS,
        ) for i, role in enumerate(roles)]
        ats_tasks.extend(SearchTask(
            intent="ats", label="job boards",
            query=_join(_role_with_level(roles[0], level), place),
            purpose="Find individual open job and internship postings that match a student's search",
            include_domains=ATS_SEARCH_DOMAINS,
        ) for place in places[len(roles):])
        primary.extend(ats_tasks[:2])
        secondary.extend(ats_tasks[2:])
        if p.needs_visa_sponsorship:
            primary.append(SearchTask(
                intent="ats", label="job boards (visa sponsorship)",
                query=_join(_role_with_level(roles[0], level), "visa sponsorship", first_place),
                purpose="Find open postings that offer visa sponsorship to international candidates",
                include_domains=ATS_SEARCH_DOMAINS,
            ))
        primary.append(SearchTask(
            intent="web", label="the web",
            query=_join(_role_with_level(roles[0], level, "internship" if level == "intern" else level), first_place, year, "apply"),
            purpose="Find company careers pages and job portals with current openings",
            exclude_domains=EXCLUDED_DOMAINS,
        ))
        if p.funding != "any":
            primary.append(SearchTask(
                intent="web",label="funding coverage",
                query=_join(_role_with_level(roles[0], level),first_place,
                            "stipend accommodation round trip travel" if p.funding=="fully_funded" else "paid stipend",year),
                purpose="Find official internship sources with explicitly stated support; search wording does not prove the benefits",
                exclude_domains=EXCLUDED_DOMAINS,
            ))
        if p.keywords:
            secondary.append(SearchTask(
                intent="ats", label="job boards (keywords)",
                query=_join(_role_with_level(roles[0], level), " ".join(p.keywords[:2]), first_place),
                purpose="Find individual open postings that mention the student's keywords",
                include_domains=ATS_SEARCH_DOMAINS,
            ))

    if "research_programs" in p.opportunity_types:
        fields = list(dict.fromkeys(field_of(role) for role in roles))
        funding_hint = {"fully_funded": "fully funded", "paid": "paid stipend", "any": "stipend"}[p.funding]
        purpose = "Find official pages of internship and research programs (universities, labs, agencies, companies) with their eligibility, funding and deadlines"
        primary.extend([
            SearchTask(intent="programs", label="research programs",
                       query=_join(funding_hint, fields[0], "research internship international students", first_place, year),
                       purpose=purpose, exclude_domains=EXCLUDED_DOMAINS),
            SearchTask(intent="programs", label="research programs",
                       query=_join("summer research program", fields[1] if len(fields) > 1 else fields[0],
                                   "undergraduate international applicants", first_place, year),
                       purpose=purpose, exclude_domains=EXCLUDED_DOMAINS),
        ])
        if p.citizenship:
            secondary.append(SearchTask(
                intent="programs", label="research programs",
                query=_join(fields[0], "research internship abroad for students from", p.citizenship, funding_hint, year),
                purpose=purpose, exclude_domains=EXCLUDED_DOMAINS,
            ))
        secondary.extend(SearchTask(
            intent="programs", label="research programs",
            query=_join(fields[0], "research internship", place, "international students", funding_hint, year),
            purpose=purpose, exclude_domains=EXCLUDED_DOMAINS,
        ) for place in places[:2])

    result: list[SearchTask] = []
    seen: set[str] = set()
    for task in [*company_tasks, *primary, *secondary]:
        key = task.query.lower()
        if key not in seen:
            result.append(task)
            seen.add(key)
    return result
