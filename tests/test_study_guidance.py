"""Offline topic-first planning checks. No providers, saved data, or graph writes."""
from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.models import Fact, GraphContext, Opportunity, Plan, PreparationTask, ProfileState, TopicInfo
from app.planner import build_plan


def graph(program="GLOBAL INTERNSHIP PROGRAM"):
    return GraphContext(opportunities=[Opportunity(
        id="target", program=program, category="Company", source_url="https://example.org/program",
        facts=[Fact(name="skills", status="unknown", excerpt="")],
    )], tasks=[PreparationTask(
        id="target/verify", title="Check application requirements", category="Company",
        hours_low=0.5, hours_high=1, target_ids=["target"],
    )])


def profile(**updates):
    values = dict(id="test-profile", study_track="software", start_date="2026-10-19",
                  horizon_weeks=8, weekly_hours=6)
    values.update(updates)
    return ProfileState(**values)


@pytest.mark.parametrize("track,expected", [
    ("software", {"programming", "data_structures", "algorithms", "complexity", "sql", "mock_interview"}),
    ("data", {"python", "statistics", "sql", "data_analysis", "machine_learning"}),
    ("research", {"research_reading", "research_methods", "project_story"}),
    ("general", {"project_story", "behavioral", "mock_interview"}),
])
def test_tracks_provide_real_topics_practice_resources_and_weekly_work(track, expected):
    plan = build_plan(graph(), profile(study_track=track))
    assert expected <= {entry.key for entry in plan.roadmap}
    assert all(entry.learn and entry.practice and entry.done_when and entry.resources for entry in plan.roadmap)
    assert all(entry.basis == "recommended" and not entry.required_by for entry in plan.roadmap)
    assert any(entry.week_allocations for entry in plan.roadmap)
    assert plan.study_hours_high > 0
    assert sum(entry.start_here for entry in plan.roadmap) == 1
    assert plan.next_action.startswith("Study next:")
    assert plan.study_hours_high + plan.application_hours_high == pytest.approx(plan.total_hours_high)


@pytest.mark.parametrize("track", ["research", "general"])
def test_non_coding_tracks_do_not_invent_a_coding_syllabus(track):
    keys = {entry.key for entry in build_plan(graph(), profile(study_track=track)).roadmap}
    assert not keys & {"programming", "algorithms", "data_structures", "python"}


@pytest.mark.parametrize("name,expected", [
    ("GLOBAL INTERNSHIP PROGRAM", "general"),
    ("Software engineering internship", "software"),
    ("Data analyst internship", "data"),
    ("Laboratory research placement", "research"),
])
def test_auto_uses_relevant_scope_and_handles_ambiguity_honestly(name, expected):
    plan = build_plan(graph(name), profile(study_track="auto"))
    assert plan.study_track == expected
    if expected == "general":
        assert "do not establish a technical interview syllabus" in plan.study_track_reason


def test_legacy_source_only_behavior_and_old_plan_deserialization_are_preserved():
    plan = build_plan(graph(), ProfileState(start_date="2026-10-19"))
    assert plan.study_track == "source_only" and not plan.roadmap
    assert len(plan.tasks) == 1
    payload = plan.model_dump(mode="json")
    for key in ("study_track", "study_track_reason", "study_hours_low", "study_hours_high",
                "application_hours_low", "application_hours_high"):
        payload.pop(key)
    payload["profile"].pop("study_track")
    assert Plan.model_validate(payload).profile.study_track == "source_only"


def test_recommendations_do_not_change_evidence_facts_assessments_or_inputs():
    context = graph()
    snapshot = deepcopy(context.model_dump())
    base = build_plan(context, profile(study_track="source_only"))
    enriched = build_plan(context, profile())
    assert context.model_dump() == snapshot
    assert enriched.targets == base.targets
    assert enriched.evidence == base.evidence and enriched.fact_versions == base.fact_versions
    study_tasks = [task for task in enriched.tasks if task.category == "Study"]
    assert study_tasks and all(not task.target_ids and not task.fact_version_ids for task in study_tasks)
    original = next(task for task in enriched.tasks if task.task_id == "target/verify")
    assert original == base.tasks[0]


def test_one_budget_respects_exam_week_holiday_and_daily_pattern():
    plan = build_plan(graph(), profile(horizon_weeks=3, weekly_pattern={"0": 2, "2": 2},
                                      exam_weeks=["2026-10-26"], holidays=["2026-10-19"]))
    assert plan.available_hours == pytest.approx(6)
    assert plan.weekly_used["2026-10-19"] <= 2 + 1e-8
    assert plan.weekly_used["2026-10-26"] == 0
    assert plan.weekly_used["2026-11-02"] <= 4 + 1e-8
    assert sum(plan.weekly_used.values()) <= plan.available_hours + 1e-8
    for week, hours in plan.weekly_used.items():
        assert hours == pytest.approx(sum(task.week_allocations.get(week, 0) for task in plan.tasks))


def test_no_capacity_and_short_horizon_are_not_presented_as_finished_plans():
    empty = build_plan(graph(), profile(weekly_hours=0, horizon_weeks=1))
    assert not any(entry.start_here for entry in empty.roadmap)
    assert not any(entry.scheduled for entry in empty.roadmap)
    assert "increase availability" in empty.next_action
    short = build_plan(graph(), profile(weekly_hours=2, horizon_weeks=1))
    assert any(entry.task_status in {"unscheduled", "blocked"} for entry in short.roadmap)
    assert sum(short.weekly_used.values()) <= 2 + 1e-8


def test_completion_undo_and_new_proposals_preserve_previous_saved_content():
    context = graph()
    original = build_plan(context, profile())
    snapshot = original.model_dump()
    topic = next(entry for entry in original.roadmap if entry.start_here)
    task_id = topic.task_ids[0]
    completed = build_plan(context, profile(completed_task_ids=[task_id]), previous=original)
    assert next(task for task in completed.tasks if task.task_id == task_id).status == "completed"
    assert task_id in completed.profile.completed_task_ids
    assert not any("outside the current graph" in message for message in completed.warnings)
    assert original.model_dump() == snapshot
    undone = build_plan(context, profile(completed_task_ids=[]), previous=completed)
    assert next(task for task in undone.tasks if task.task_id == task_id).status != "completed"
    assert task_id not in undone.profile.completed_task_ids
    assert original.id != completed.id != undone.id


def test_comfortable_shortens_only_recommended_practice_not_source_required_work():
    context = graph()
    key = "shared/skill-python-foundation/v1"
    context.tasks.append(PreparationTask(id=key, title="Source-linked Python practice",
                                        hours_low=2, hours_high=4, target_ids=["target"]))
    context.topics.append(TopicInfo(key="python", title="Python", required_by={"target": ["skills"]}))
    plan = build_plan(context, profile(study_track="data", skill_ratings={"python": "comfortable", "statistics": "comfortable"}))
    python = next(entry for entry in plan.roadmap if entry.key == "python")
    assert python.basis == "source_linked" and python.hours_high == 4
    assert python.task_ids == [key]
    assert len([entry for entry in plan.roadmap if entry.key == "python"]) == 1
    statistics = next(entry for entry in plan.roadmap if entry.key == "statistics")
    assert statistics.hours_high == 1 and statistics.task_status != "completed"


def test_prerequisites_and_task_dependencies_are_present_and_ordered():
    plan = build_plan(graph(), profile(study_track="data"))
    tasks = {task.task_id: task for task in plan.tasks}
    position = {entry.key: index for index, entry in enumerate(plan.roadmap)}
    for entry in plan.roadmap:
        for prerequisite in entry.prerequisites:
            assert position[prerequisite] < position[entry.key]
        for task_id in entry.task_ids:
            assert set(tasks[task_id].dependencies) <= tasks.keys()
    active = next(entry for entry in plan.roadmap if entry.start_here)
    assert all(tasks[dependency].status == "completed"
               for task_id in active.task_ids for dependency in tasks[task_id].dependencies)
    assert Plan.model_validate_json(plan.model_dump_json()) == plan


def test_unknown_track_is_rejected_instead_of_silently_falling_back():
    with pytest.raises(ValidationError):
        profile(study_track="invent-a-job")
