from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.discovery.contracts import DiscoveryPreferences, RunBudget
from app.discovery.search_plan import ATS_SEARCH_DOMAINS, EXCLUDED_DOMAINS, field_of, plan_searches, target_year


CLOCK = datetime(2026, 10, 16, tzinfo=timezone.utc)


def test_scout_preference_aliases_and_full_surface():
    p = DiscoveryPreferences.model_validate({
        "roles": [" software engineering intern "], "keywords": ["Python"],
        "excludeKeywords": ["senior"], "locations": ["Germany"], "remoteOk": True,
        "seniority": ["internship"], "opportunityTypes": ["company_roles"],
        "needsVisaSponsorship": True, "citizenship": "India", "funding": "paid",
        "companies": ["Amazon"],
    })
    assert p.roles == ["software engineering intern"]
    assert p.exclude_keywords == ["senior"]
    assert p.model_dump(by_alias=True)["needsVisaSponsorship"] is True


@pytest.mark.parametrize("value", [[], ["   "], ["engineer"] * 6])
def test_invalid_role_preferences_rejected(value):
    with pytest.raises(ValidationError):
        DiscoveryPreferences(roles=value)


def test_company_searches_come_before_primary_and_secondary_queries():
    p = DiscoveryPreferences(
        roles=["software engineering intern"], locations=["Germany"],
        companies=["Amazon"], needs_visa_sponsorship=True, keywords=["Python"],
        citizenship="India", funding="paid",
    )
    tasks = plan_searches(p, CLOCK)
    assert [t.query for t in tasks] == [
        "Amazon careers software engineering intern",
        "software engineering intern Germany",
        "software engineering intern visa sponsorship Germany",
        "software engineering intern Germany 2027 apply",
        "software engineering intern Germany paid stipend 2027",
        "paid stipend software engineering research internship international students Germany 2027",
        "summer research program software engineering undergraduate international applicants Germany 2027",
        "software engineering intern Python Germany",
        "software engineering research internship abroad for students from India paid stipend 2027",
        "software engineering research internship Germany international students paid stipend 2027",
    ]
    assert tasks[0].intent == "company" and tasks[0].company == "Amazon"
    assert "indeed.com" in tasks[0].exclude_domains
    assert tasks[1].include_domains == ATS_SEARCH_DOMAINS


def test_research_only_does_not_emit_job_board_queries():
    p = DiscoveryPreferences(roles=["machine learning intern"], opportunity_types=["research_programs"], funding="fully_funded")
    tasks = plan_searches(p, CLOCK)
    assert all(t.intent == "programs" for t in tasks)
    assert tasks[0].query.startswith("fully funded machine learning research internship")


def test_company_only_does_not_emit_program_queries():
    p = DiscoveryPreferences(roles=["software engineer"], opportunity_types=["company_roles"])
    assert {t.intent for t in plan_searches(p, CLOCK)} == {"ats", "web"}


def test_remote_search_hint_and_no_duplicate_level_word():
    tasks = plan_searches(DiscoveryPreferences(roles=["Machine learning intern"], remote_ok=True), CLOCK)
    assert tasks[0].query == "Machine learning intern remote"
    assert all("intern intern" not in t.query.lower() for t in tasks)


def test_extra_roles_and_places_stay_secondary_and_queries_deduplicate():
    p = DiscoveryPreferences(roles=["Software Engineer", "Data Scientist", "Researcher"], locations=["Germany", "Japan", "Canada"], companies=["Amazon", "amazon"])
    tasks = plan_searches(p, CLOCK)
    queries = [t.query.lower() for t in tasks]
    assert len(queries) == len(set(queries))
    assert [t.query for t in tasks[:3]] == ["Amazon careers Software Engineer intern", "Software Engineer intern Germany", "Data Scientist intern Japan"]
    assert next(i for i, t in enumerate(tasks) if t.query == "Researcher intern Canada") > next(i for i, t in enumerate(tasks) if t.intent == "programs")


@pytest.mark.parametrize("role,expected", [
    ("Machine Learning Engineer Intern", "machine learning"),
    ("Data Scientist / Research Intern", "data research"),
    ("Intern", "intern"),
])
def test_research_field_extraction(role, expected):
    assert field_of(role) == expected


@pytest.mark.parametrize("month,year", [(6, 2026), (7, 2027), (12, 2027)])
def test_target_year_is_only_a_search_hint(month, year):
    assert target_year(datetime(2026, month, 1, tzinfo=timezone.utc)) == year


def test_search_year_uses_utc_boundary_and_rejects_naive_clock():
    assert target_year(datetime.fromisoformat("2026-07-01T00:00:00+05:30")) == 2026
    with pytest.raises(ValueError, match="timezone-aware"):
        target_year(datetime(2026, 7, 1))


def test_scout_run_ceilings_are_preserved_without_spend_authorization():
    budget = RunBudget()
    assert (budget.max_searches, budget.max_fetch_urls, budget.max_agent_runs) == (12, 45, 2)
    assert (budget.max_extractions, budget.max_boards, budget.max_rechecks) == (36, 8, 6)
    assert (budget.soft_deadline_ms, budget.hard_deadline_ms) == (150_000, 270_000)
    assert RunBudget(max_agent_runs=0).max_agent_runs == 0
    with pytest.raises(ValidationError):
        RunBudget(max_agent_runs=3)


def test_budget_rejects_soft_deadline_after_hard_deadline():
    with pytest.raises(ValidationError, match="Soft deadline"):
        RunBudget(hard_deadline_ms=1000)
    assert RunBudget(soft_deadline_ms=1000, hard_deadline_ms=1000).hard_deadline_ms == 1000


@pytest.mark.parametrize("seniority,expected", [
    (["experienced", "new_grad", "internship"], "software engineer intern"),
    (["entry_level", "new_grad"], "software engineer new grad"),
    (["experienced", "entry_level"], "software engineer entry level"),
    (["experienced"], "software engineer"),
])
def test_mixed_seniority_uses_scout_precedence(seniority, expected):
    p = DiscoveryPreferences(roles=["software engineer"], seniority=seniority, opportunity_types=["company_roles"])
    assert plan_searches(p, CLOCK)[0].query == expected


def test_research_only_keeps_named_company_searches():
    p = DiscoveryPreferences(roles=["robotics intern"], companies=["OIST"], opportunity_types=["research_programs"])
    tasks = plan_searches(p, CLOCK)
    assert tasks[0].intent == "company"
    assert tasks[0].query == "OIST careers robotics intern"
    assert all(t.intent == "programs" for t in tasks[1:])


def test_scout_search_domain_lists_are_preserved():
    assert ATS_SEARCH_DOMAINS == (
        "job-boards.greenhouse.io", "boards.greenhouse.io", "jobs.lever.co",
        "myworkdayjobs.com", "jobs.smartrecruiters.com", "apply.workable.com",
    )
    assert EXCLUDED_DOMAINS == (
        "linkedin.com", "indeed.com", "glassdoor.com", "glassdoor.co.in",
        "ziprecruiter.com", "monster.com", "simplyhired.com", "facebook.com",
        "instagram.com", "twitter.com", "x.com", "youtube.com", "reddit.com",
        "quora.com", "pinterest.com", "tiktok.com", "levels.fyi", "teamblind.com",
    )


def test_query_generation_caps_first_three_roles_and_places_like_scout():
    p = DiscoveryPreferences(
        roles=["AI intern", "ML intern", "Data intern", "Security intern", "Robotics intern"],
        locations=["Germany", "Japan", "Canada", "France", "Spain", "Italy"],
    )
    queries = "\n".join(t.query for t in plan_searches(p, CLOCK))
    assert "Data intern Canada" in queries
    assert not any(value in queries for value in ["Security", "Robotics", "France", "Spain", "Italy"])
