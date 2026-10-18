"""Roadmap slice: topic catalog, self-reported ratings, per-day timetable.

Pure planner cases plus one disposable real-FalkorDB round trip. Unavailable
storage skips explicitly; it is never replaced by a mocked graph.
"""

from __future__ import annotations

import os
from dataclasses import replace
from uuid import uuid4

import pytest
from falkordb import FalkorDB
from redis.exceptions import RedisError

from app.config import settings
from app.graph import GraphStore
from app.models import Fact, GraphContext, Opportunity, ProfileState, TopicInfo
from app.planner import build_plan
from app.topics import catalog_rows, fact_topic_keys, prerequisite_closure, topic_keys_for


def fact(name, value, *, excerpt="Skills: Python and Docker.", status="known"):
    return Fact(name=name, value=value, status=status, kind="requirement",
                excerpt=excerpt, source_url="https://example.org/source")


def opportunity(target="roadmap-target", *, skills=("Python", "Docker")):
    return Opportunity(id=target, program="Roadmap Test Program", category="Company",
                       source_url="https://example.org/source", mode="synthetic",
                       call_status="open", verification="partial",
                       facts=[fact("skills", list(skills), excerpt="Required: " + ", ".join(skills) + ".")])


def task(task_id, *, targets=("roadmap-target",), low=1, high=1, facts=(), category="Company"):
    from app.models import PreparationTask
    return PreparationTask(id=task_id, title=task_id, category=category, hours_low=low, hours_high=high,
                           target_ids=list(targets), fact_names=list(facts), provenance="test")


def context(opportunities, tasks, topics):
    return GraphContext(opportunities=opportunities, tasks=tasks, topics=topics)


def topic(key, *, title, prereqs=(), required_by=None, resources=None):
    return TopicInfo(key=key, title=title, family="Test", prerequisites=list(prereqs),
                     resources=list(resources or []), required_by=required_by or {})


# --- catalog ---------------------------------------------------------------

def test_catalog_closure_includes_prerequisites_once_in_order():
    closure = prerequisite_closure(["machine_learning", "docker"])
    assert closure.index("linux") < closure.index("docker")
    assert closure.index("python") < closure.index("machine_learning")
    assert closure.count("python") == 1
    assert set(closure) == {"machine_learning", "docker", "linux", "python", "statistics", "data_structures", "programming"}


def test_language_alternatives_collapse_to_programming_topic():
    assert fact_topic_keys("programming_languages", ["Java", "Python"],
                           "Experience with one of Java or Python.") == ["programming"]
    assert fact_topic_keys("programming_languages", ["Java", "Python"],
                           "Java and Python required.") == ["java", "python"]
    assert fact_topic_keys("skills", ["Kubernetes"], "Runs Kubernetes.") == []


def test_topic_keys_skip_unknown_or_excerptless_facts():
    unknown = opportunity(skills=["Python"])
    unknown.facts[0].status = "unknown"
    assert topic_keys_for(unknown) == []
    excerptless = opportunity(skills=["Python"])
    excerptless.facts[0].excerpt = "  "
    assert topic_keys_for(excerptless) == []
    unknown_skill = opportunity(skills=["Kubernetes"])
    assert topic_keys_for(unknown_skill) == []


def test_catalog_rows_carry_payload_resources_and_edges():
    rows = catalog_rows(prerequisite_closure(["docker"]))
    keys = {row["key"] for row in rows["topics"]}
    assert {"docker", "linux"} <= keys
    docker = next(row for row in rows["topics"] if row["key"] == "docker")
    assert docker["prerequisites"] == ["linux"]
    assert rows["edges"] == [{"topic": "docker", "prerequisite": "linux"}]
    assert all(row["provenance"] == "authored_guide" for row in rows["resources"])


# --- profile validation ----------------------------------------------------

def test_invalid_ratings_and_patterns_are_pruned_not_crashing():
    state = ProfileState(skill_ratings={"python": "expert", "ml": "new", "x": 3},
                         weekly_pattern={"0": 2, "7": 3, "3": -1, "5": "4", "z": 1})
    assert state.skill_ratings == {"ml": "new"}
    assert state.weekly_pattern == {"0": 2.0, "5": 4.0}


# --- timestamped availability ---------------------------------------------

def test_pattern_replaces_even_spread_and_caps_capacity():
    graph = context([opportunity()], [task("prep", high=2)], [])
    even = build_plan(graph, ProfileState(start_date="2026-10-19", horizon_weeks=1, weekly_hours=7))
    assert even.available_hours == pytest.approx(7)
    pattern = build_plan(graph, ProfileState(start_date="2026-10-19", horizon_weeks=1,
                                             weekly_pattern={"5": 4.0, "6": 2.0}))
    assert pattern.available_hours == pytest.approx(6)
    assert not any("spread evenly" in warning for warning in pattern.warnings)
    assert any("per-day pattern" in warning for warning in pattern.warnings)


def test_holiday_removes_day_capacity_and_invalid_holiday_is_reported():
    graph = context([opportunity()], [task("prep", high=2)], [])
    state = ProfileState(start_date="2026-10-19", horizon_weeks=1, weekly_hours=7, holidays=["2026-10-21"])
    plan = build_plan(graph, state)
    assert plan.available_hours == pytest.approx(6)
    invalid = build_plan(graph, ProfileState(start_date="2026-10-19", horizon_weeks=1, weekly_hours=7,
                                             holidays=["not-a-date"]))
    assert invalid.available_hours == pytest.approx(7)
    assert any("not an ISO calendar date" in warning for warning in invalid.warnings)


def test_multiple_exam_weeks_stay_protected():
    graph = context([opportunity()], [task("prep", high=1)], [])
    state = ProfileState(start_date="2026-10-19", horizon_weeks=3, weekly_hours=7,
                         exam_weeks=["2026-10-26", "2026-11-02"])
    plan = build_plan(graph, state)
    assert plan.available_hours == pytest.approx(7)
    assert plan.weekly_used["2026-10-26"] == pytest.approx(0)
    assert plan.weekly_used["2026-11-02"] == pytest.approx(0)


# --- roadmap ---------------------------------------------------------------

def test_roadmap_orders_prerequisites_and_respects_self_reported_ratings():
    topics = [
        topic("linux", title="Linux", required_by={}),
        topic("docker", title="Docker", prereqs=["linux"]),
        topic("python", title="Python", required_by={"roadmap-target": ["skills"]},
              resources=[{"title": "Python tutorial", "url": "https://docs.python.org/3/tutorial/"}]),
        topic("machine_learning", title="ML", prereqs=["python"], required_by={"roadmap-target": ["skills"]}),
    ]
    tasks = [task("shared/skill-python-foundation/v1", category="Shared", facts=[]),
             task("shared/skill-machine_learning-foundation/v1", category="Shared", facts=[])]
    graph = context([opportunity()], tasks, topics)
    graph.opportunities[0].facts[0].value = ["Python", "Machine Learning"]
    plan = build_plan(graph, ProfileState(start_date="2026-10-19", horizon_weeks=4))
    roadmap = plan.roadmap
    assert [entry.key for entry in roadmap] == ["linux", "docker", "python", "machine_learning"]
    by_key = {entry.key: entry for entry in roadmap}
    assert by_key["python"].start_here and not by_key["machine_learning"].start_here
    assert not by_key["linux"].task_ids and "Prerequisite" in by_key["linux"].note
    assert by_key["linux"].order == 1 and by_key["machine_learning"].order == 4
    assert by_key["python"].resources[0]["title"] == "Python tutorial"
    assert any("authored practice topics" in warning for warning in plan.warnings)

    rated = build_plan(graph, ProfileState(start_date="2026-10-19", horizon_weeks=4,
                                           skill_ratings={"python": "comfortable"}))
    rated_by_key = {entry.key: entry for entry in rated.roadmap}
    assert not rated_by_key["python"].start_here
    assert rated_by_key["machine_learning"].start_here
    assert any("marked this comfortable" in entry.note for entry in rated.roadmap if entry.key == "python")


def test_no_topics_means_no_roadmap_and_no_warning():
    graph = context([opportunity()], [task("prep")], [])
    plan = build_plan(graph, ProfileState(start_date="2026-10-19"))
    assert plan.roadmap == []
    assert not any("authored practice topics" in warning for warning in plan.warnings)


# --- graph round trip ------------------------------------------------------

@pytest.fixture
def store():
    graph_name = f"just_chill_test_{uuid4().hex}"
    test_settings = replace(settings, db_graph=graph_name)
    graph_store = GraphStore(test_settings)
    if graph_store.health()["status"] != "ok":
        if os.getenv("REQUIRE_FALKORDB") == "1":
            pytest.fail("Real FalkorDB is unavailable; graph proof cannot pass.")
        pytest.skip("Real FalkorDB is unavailable; no mocked graph proof substituted.")
    try:
        yield graph_store
    finally:
        assert graph_name.startswith("just_chill_test_")
        assert graph_name != settings.db_graph
        try:
            client = FalkorDB(host=test_settings.db_host, port=test_settings.db_port,
                              password=test_settings.db_password,
                              socket_connect_timeout=3, socket_timeout=5)
            if graph_name in client.list_graphs():
                client.select_graph(graph_name).delete()
            client.close()
        except RedisError:
            pytest.fail("Could not clean up the disposable graph; main graph was never deleted.")


def test_graph_round_trip_writes_topics_prerequisites_and_fact_links(store):
    target = opportunity("graph-roadmap-1", skills=["Python", "Docker"])
    store.upsert_opportunity(target)
    loaded = store.context(["graph-roadmap-1"])
    keys = {item.key for item in loaded.topics}
    assert {"python", "docker", "linux"} <= keys
    docker = next(item for item in loaded.topics if item.key == "docker")
    assert "linux" in docker.prerequisites
    python = next(item for item in loaded.topics if item.key == "python")
    assert python.required_by == {"graph-roadmap-1": ["skills"]}
    assert python.resources, "authored resources travel through the graph payload"
    plan = build_plan(loaded, ProfileState(start_date="2026-10-19", horizon_weeks=6))
    order = [entry.key for entry in plan.roadmap]
    assert order.index("linux") < order.index("docker")
    by_key = {entry.key: entry for entry in plan.roadmap}
    assert by_key["python"].task_ids and by_key["python"].task_status in {"scheduled", "blocked", "unscheduled"}
    # A changed skills fact rewrites the fact links without losing topic nodes.
    changed = opportunity("graph-roadmap-1", skills=["Java"])
    changed.facts.append(fact("application_deadline", "2026-12-01T00:00:00+05:30", excerpt="Apply by 1 December 2026."))
    store.upsert_opportunity(changed)
    reloaded = store.context(["graph-roadmap-1"])
    assert "python" not in {item.key for item in reloaded.topics}
    assert "java" in {item.key for item in reloaded.topics}
    assert store.backfill_topics() == 1
    assert "java" in {item.key for item in store.context(["graph-roadmap-1"]).topics}
