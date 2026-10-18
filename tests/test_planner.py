from __future__ import annotations

from copy import deepcopy

import pytest

from app.models import (
    ChangeImpact,
    Fact,
    FactChange,
    GraphContext,
    Opportunity,
    PreparationTask,
    ProfileState,
)
from app.planner import build_plan


def fact(name, value, *, target="research", kind="requirement", status="known", version=None):
    return Fact(
        name=name, value=value, kind=kind, status=status,
        excerpt=f"Synthetic fixture: {name} = {value}.",
        source_url=f"https://example.org/{target}",
        version_id=version or f"{target}/{name}/v1", simulated=True,
    )


def opportunity(target="research", *, category="Research", deadline="2026-12-14T23:59:00+05:30", portal="open", extras=()):
    return Opportunity(
        id=target, program=target, cycle="fixture-2026", category=category,
        source_url=f"https://example.org/{target}", call_status=portal,
        verification="verified", mode="synthetic",
        facts=[
            fact("application_deadline", deadline, target=target, status="known" if deadline else "unknown"),
            fact("portal_status", portal, target=target, kind="information"),
            fact("degree_levels", ["bachelor"], target=target),
            fact("documents", ["cv"], target=target),
            *extras,
        ],
    )


def task(task_id, *, targets=("research",), low=1, high=1, dependencies=(), waiting=None, category="Research", facts=(), artifact=""):
    return PreparationTask(
        id=task_id, title=task_id, category=category, hours_low=low, hours_high=high,
        target_ids=list(targets), dependencies=list(dependencies), waiting_for=waiting,
        fact_names=list(facts), artifact_type=artifact, provenance="synthetic_test_recipe",
    )


def context(opportunities, tasks):
    return GraphContext(
        opportunities=list(opportunities), tasks=list(tasks),
        fact_versions={f"{item.id}/{condition.name}": condition.version_id for item in opportunities for condition in item.facts},
    )


def profile(**updates):
    defaults = dict(country="India", degree="BTech", field="computer_science", year=3,
                    total_years=4, institution_type="non_iit", synthetic=True)
    return ProfileState(start_date="2026-10-19", horizon_weeks=8, exam_weeks=[], **(defaults | updates))


def tasks_by_id(plan):
    return {task.task_id: task for task in plan.tasks}


def test_shared_work_is_counted_once_and_final_documents_remain_distinct():
    research = opportunity()
    company = opportunity("company", category="Company")
    graph = context([research, company], [
        task("shared/cv-base/v1", targets=(), category="Shared", low=1, high=2),
        task("research/cv-final/v1", dependencies=["shared/cv-base/v1"], facts=["documents"]),
        task("company/cv-final/v1", targets=["company"], category="Company", dependencies=["shared/cv-base/v1"], facts=["documents"]),
    ])
    plan = build_plan(graph, profile(weekly_hours=4))
    assert len(plan.tasks) == 3
    assert plan.total_hours_high == 4
    shared = tasks_by_id(plan)["shared/cv-base/v1"]
    assert shared.target_ids == ["company", "research"]
    assert shared.fact_version_ids == []
    assert all(target.schedule_status == "feasible" for target in plan.targets)
    assert all(hours <= 4 + 1e-8 for hours in plan.weekly_used.values())


def test_same_id_with_incompatible_final_document_recipes_blocks_certification():
    graph = context([opportunity(), opportunity("other")], [
        task("same/final", facts=["statement_max_words"]),
        task("same/final", targets=["other"], facts=["statement_max_chars"]),
    ])
    plan = build_plan(graph, profile())
    assert tasks_by_id(plan)["same/final"].status == "blocked"
    assert any("incompatible recipes" in warning for warning in plan.warnings)
    assert all(target.schedule_status != "feasible" for target in plan.targets)


def test_requesting_reference_does_not_assume_receipt_or_schedule_submission():
    event = "research/references_received/min=1/by=recommender/before_submit=true"
    graph = context([opportunity()], [
        task("request", artifact="reference_request"),
        task("receipt", low=0, high=0, dependencies=["request"], waiting=event, artifact="reference_receipt"),
        task("submit", dependencies=["receipt"], artifact="submission"),
    ])
    plan = build_plan(graph, profile())
    rows = tasks_by_id(plan)
    assert rows["request"].status == "scheduled"
    assert rows["receipt"].status == "waiting"
    assert rows["receipt"].week_allocations == {}
    assert rows["submit"].status == "blocked"
    assert rows["submit"].week_allocations == {}
    assert plan.targets[0].readiness == "waiting_external"
    assert plan.targets[0].schedule_status == "cannot_certify"
    assert plan.next_action == "request"
    observed = build_plan(graph, profile(completed_task_ids=["request"], received_events=[event]), previous=plan)
    assert tasks_by_id(observed)["receipt"].status == "completed"
    assert tasks_by_id(observed)["submit"].status == "scheduled"
    assert observed.targets[0].schedule_status == "feasible"


def test_old_receipt_does_not_satisfy_a_changed_reference_count():
    old_event = "research/references_received/min=1/by=recommender/before_submit=true"
    new_event = "research/references_received/min=2/by=recommender/before_submit=true"
    initial = context([opportunity(extras=[fact("reference_min", 1)])], [
        task("shared", targets=(), category="Shared"),
        task("request", facts=["reference_min"]),
        task("receipt", low=0, high=0, dependencies=["request"], waiting=old_event, facts=["reference_min"]),
        task("submit", dependencies=["shared", "receipt"], artifact="submission"),
    ])
    previous = build_plan(initial, profile(completed_task_ids=["shared", "request"], received_events=[old_event]))
    modified = deepcopy(initial)
    modified.opportunities[0].facts[-1] = fact("reference_min", 2, version="new-ref-version")
    modified.fact_versions["research/reference_min"] = "new-ref-version"
    modified.tasks[2].waiting_for = new_event
    impact = ChangeImpact(
        semantic_change=True, affected_target_ids=["research"], affected_task_ids=["request", "receipt", "submit"],
        changes=[FactChange(opportunity_id="research", fact_name="reference_min", old_version_id="research/reference_min/v1", new_version_id="new-ref-version", old_value=1, new_value=2)],
    )
    revised = build_plan(modified, previous.profile, previous=previous, impact=impact)
    rows = tasks_by_id(revised)
    assert rows["shared"].status == "completed"
    assert rows["request"].status == "scheduled"
    assert rows["receipt"].status == "waiting"
    assert rows["submit"].status == "blocked"
    assert revised.affected_task_ids == ["request", "receipt", "submit"]


def test_research_company_and_shared_use_combined_capacity_and_exam_blackout():
    graph = context([opportunity(), opportunity("company", category="Company")], [
        task("shared", targets=(), category="Shared", low=3, high=5),
        task("research-final", low=5, high=8, dependencies=["shared"]),
        task("company-final", targets=["company"], category="Company", low=5, high=8, dependencies=["shared"]),
    ])
    state = ProfileState(start_date="2026-10-19", horizon_weeks=5, weekly_hours=6, exam_weeks=["2026-11-02"])
    plan = build_plan(graph, state)
    assert plan.available_hours == 24
    assert plan.weekly_used["2026-11-02"] == 0
    assert all(hours <= 6 + 1e-8 for hours in plan.weekly_used.values())
    assert sum(plan.weekly_used.values()) == pytest.approx(21)
    assert all(row.week_allocations.get("2026-11-02", 0) == 0 for row in plan.tasks)


def test_midweek_cutoff_prorates_availability_without_false_infeasible_claim():
    graph = context([opportunity(deadline="2026-10-20T00:00:00+05:30")], [task("one", low=1, high=2)])
    plan = build_plan(graph, profile(weekly_hours=7))
    assert sum(plan.weekly_used.values()) <= 1 + 1e-8
    assert tasks_by_id(plan)["one"].status == "unscheduled"
    assert plan.targets[0].schedule_status == "at_risk"
    assert not any("Proven combined" in warning for warning in plan.warnings)


def test_true_combined_lower_bound_shortfall_is_proven_without_double_counting():
    cutoff = "2026-10-26T00:00:00+05:30"
    graph = context([opportunity(deadline=cutoff), opportunity("other", deadline=cutoff)], [
        task("shared", targets=(), category="Shared", low=3, high=3),
        task("a", low=3, high=3, dependencies=["shared"]),
        task("b", targets=["other"], low=3, high=3, dependencies=["shared"]),
    ])
    plan = build_plan(graph, profile(weekly_hours=7))
    assert plan.total_hours_low == 9
    assert all(item.schedule_status == "infeasible" for item in plan.targets)
    assert any("9 estimated hours" in warning and "7-hour" in warning for warning in plan.warnings)


def test_descendant_is_not_allocated_ahead_of_a_full_week_predecessor():
    graph = context([opportunity()], [
        task("a-successor", dependencies=["z-predecessor"]),
        task("z-predecessor", low=7, high=7),
    ])
    plan = build_plan(graph, profile(weekly_hours=7))
    rows = tasks_by_id(plan)
    assert rows["z-predecessor"].week_allocations == pytest.approx({"2026-10-19": 7})
    assert rows["a-successor"].week_allocations == pytest.approx({"2026-10-26": 1})


@pytest.mark.parametrize("dependencies", [["missing"], ["second"]])
def test_missing_prerequisite_or_cycle_never_certifies(dependencies):
    items = [task("first", dependencies=dependencies)]
    if "second" in dependencies:
        items.append(task("second", dependencies=["first"]))
    plan = build_plan(context([opportunity()], items), profile())
    assert plan.targets[0].schedule_status == "cannot_certify"
    assert all(row.status == "blocked" and not row.week_allocations for row in plan.tasks)


def test_future_preparation_uses_shared_work_and_expired_call_is_excluded():
    graph = context([
        opportunity(), opportunity("future", portal="closed"),
        opportunity("expired", portal="closed", deadline="2026-10-18T23:59:00+05:30"),
    ], [
        task("shared", targets=(), category="Shared"),
        task("current-cv", dependencies=["shared"]),
        task("future-cv", targets=["future"], dependencies=["shared"]),
        task("future-submit", targets=["future"], dependencies=["future-cv"], artifact="submission"),
        task("expired-cv", targets=["expired"], dependencies=["shared"]),
    ])
    plan = build_plan(graph, profile())
    assessments = {item.target_id: item for item in plan.targets}
    rows = tasks_by_id(plan)
    assert assessments["future"].call_status == "closed"
    assert assessments["future"].readiness == "preparation_only"
    assert assessments["future"].schedule_status == "cannot_certify"
    assert assessments["expired"].schedule_status == "excluded"
    assert rows["future-cv"].status == "scheduled"
    assert rows["future-submit"].status == "blocked"
    assert rows["expired-cv"].status == "unscheduled"
    assert sum(plan.weekly_used.values()) == pytest.approx(3)


def test_unknown_deadline_is_not_certified_even_when_preparation_fits():
    plan = build_plan(context([opportunity(deadline=None)], [task("prep")]), profile())
    assert tasks_by_id(plan)["prep"].status == "scheduled"
    assert plan.targets[0].schedule_status == "cannot_certify"
    assert "missing" in " ".join(plan.targets[0].reasons)


def test_unknown_requirement_is_not_treated_as_met_but_preference_is_never_exclusion():
    graph = context([opportunity(extras=[
        fact("onsite_required", True),
        fact("work_authorization_preference", "Singapore right to work", kind="preference"),
    ])], [task("prep")])
    plan = build_plan(graph, profile(right_to_work_singapore=False))
    target = plan.targets[0]
    conditions = {item.name: item for item in target.criteria}
    assert conditions["onsite_required"].status == "unknown"
    assert conditions["work_authorization_preference"].status == "preference"
    assert target.eligibility == "needs_review"
    assert target.schedule_status == "cannot_certify"


def test_institution_listed_does_not_prove_home_institution_approval():
    graph = context([opportunity(extras=[fact("institution_approval", True)])], [task("prep")])
    plan = build_plan(graph, profile(institution_listed=True))
    assert next(item for item in plan.targets[0].criteria if item.name == "institution_approval").status == "unknown"
    observed = build_plan(graph, profile(received_events=["research/institution_approval_confirmed"]))
    assert next(item for item in observed.targets[0].criteria if item.name == "institution_approval").status == "met"


def test_sourced_field_exception_keeps_different_field_in_review():
    graph = context([opportunity(extras=[
        fact("fields", ["computer_science"]),
        fact("field_evidence_exception", True, kind="information"),
    ])], [task("prep")])
    plan = build_plan(graph, profile(field="mathematics"))
    assert plan.targets[0].eligibility == "needs_review"
    assert "research/field_evidence_exception/v1" in plan.targets[0].used_fact_versions


def test_final_two_years_condition_uses_program_length_and_honors_future_unknown():
    condition = {"type": "final_two_years", "applies_to": ["bachelor"], "assessed_at": "application_or_internship_start", "graduates_allowed": True}
    graph = context([opportunity(extras=[fact("year_constraint", condition)])], [task("prep")])
    final_years = build_plan(graph, profile(year=2, total_years=3))
    assert next(item for item in final_years.targets[0].criteria if item.name == "year_constraint").status == "met"
    earlier = build_plan(graph, profile(year=2, total_years=5))
    assert next(item for item in earlier.targets[0].criteria if item.name == "year_constraint").status == "unknown"


def test_noop_refresh_preserves_task_content_allocations_and_fact_dependencies():
    graph = context([opportunity()], [
        task("shared", targets=(), category="Shared"),
        task("final", dependencies=["shared"], facts=["documents"]),
    ])
    previous = build_plan(graph, profile(completed_task_ids=["shared"]))
    before = graph.model_dump()
    revised = build_plan(graph, previous.profile, previous=previous, impact=ChangeImpact())
    assert [row.model_dump() for row in previous.tasks] == [row.model_dump() for row in revised.tasks]
    assert previous.weekly_used == revised.weekly_used
    assert previous.fact_versions == revised.fact_versions
    assert revised.affected_target_ids == revised.affected_task_ids == []
    assert graph.model_dump() == before


def test_one_target_update_preserves_other_target_and_completed_shared_work():
    a = opportunity(extras=[fact("statement_max_words", 400)])
    b = opportunity("other")
    graph = context([a, b], [
        task("shared", targets=(), category="Shared", low=1, high=2),
        task("research-final", dependencies=["shared"], facts=["statement_max_words"]),
        task("other-final", targets=["other"], dependencies=["shared"], facts=["documents"]),
    ])
    previous = build_plan(graph, profile(completed_task_ids=["shared", "other-final"]))
    modified = deepcopy(graph)
    modified.opportunities[0].facts[-1] = fact("statement_max_words", 300, version="changed-statement")
    modified.fact_versions["research/statement_max_words"] = "changed-statement"
    # Changed planning estimates do not erase an actual compatible shared artifact.
    modified.tasks[0].hours_high = 3
    impact = ChangeImpact(
        semantic_change=True, affected_target_ids=["research"], affected_task_ids=["research-final"],
        changes=[FactChange(opportunity_id="research", fact_name="statement_max_words", old_value=400, new_value=300)],
    )
    revised = build_plan(modified, previous.profile, previous=previous, impact=impact)
    rows = tasks_by_id(revised)
    assert rows["shared"].status == "completed"
    assert rows["other-final"].status == "completed"
    assert rows["other-final"].fact_version_ids == ["other/documents/v1"]
    assert rows["shared"].fact_version_ids == []
    assert revised.affected_target_ids == ["research"]


def test_unused_information_placeholders_do_not_stale_target_decisions():
    target = opportunity(extras=[fact("funding", None, kind="information", status="unknown"), fact("fee_amount", 0, kind="information")])
    graph = context([target], [task("prep", facts=["documents"])])
    plan = build_plan(graph, profile())
    assert "research/funding" not in plan.fact_versions
    assert "research/fee_amount" not in plan.fact_versions
    assert "research/funding/v1" not in plan.targets[0].used_fact_versions
    assert tasks_by_id(plan)["prep"].fact_version_ids == ["research/documents/v1"]


def test_source_uncertainty_blocks_current_certification():
    target = opportunity()
    target.verification = "uncertain"
    plan = build_plan(context([target], [task("prep")]), profile())
    assert plan.targets[0].schedule_status == "cannot_certify"
    assert plan.targets[0].eligibility == "needs_review"


def test_malformed_typed_conditions_are_unknown_instead_of_crashing():
    target = opportunity(extras=[
        fact("transcript_translation", {"unexpected": True}),
        fact("min_study_year", True),
        fact("degree_levels", None),
    ])
    # Replace duplicate eligibility condition with the malformed value.
    target.facts = [item for index, item in enumerate(target.facts) if item.name != "degree_levels" or index == len(target.facts) - 1]
    plan = build_plan(context([target], [task("prep")]), profile())
    assert plan.targets[0].eligibility == "needs_review"
    assert plan.targets[0].schedule_status == "cannot_certify"


def test_invalid_exam_input_blocks_all_allocation_and_certification():
    state = ProfileState(start_date="2026-10-19", exam_weeks=["2026-11-03"])
    plan = build_plan(context([opportunity()], [task("prep")]), state)
    assert plan.available_hours == 0
    assert all(value == 0 for value in plan.weekly_used.values())
    assert plan.targets[0].schedule_status == "cannot_certify"


def test_expired_target_cutoff_does_not_poison_shared_active_work():
    active = opportunity()
    expired = opportunity("expired", portal="closed", deadline="2026-10-18T23:59:00+05:30")
    shared = task("shared", targets=["research", "expired"], category="Shared")
    # GraphStore attaches the earliest selected cutoff; planner must derive the
    # relevant active cutoff rather than inheriting the excluded target's date.
    shared.due_at = "2026-10-18T23:59:00+05:30"
    plan = build_plan(context([active, expired], [
        shared, task("active-final", dependencies=["shared"]),
        task("expired-final", targets=["expired"], dependencies=["shared"]),
    ]), profile())
    rows = tasks_by_id(plan)
    assert rows["shared"].status == "scheduled"
    assert rows["active-final"].status == "scheduled"
    assert next(item for item in plan.targets if item.target_id == "research").schedule_status == "feasible"
    assert next(item for item in plan.targets if item.target_id == "expired").schedule_status == "excluded"


def test_observed_receipt_cannot_release_work_before_request_predecessor_is_allocated():
    event = "research/references_received/min=1/by=recommender/before_submit=true"
    graph = context([opportunity()], [
        task("request", low=7, high=7),
        task("receipt", low=0, high=0, dependencies=["request"], waiting=event),
        task("submit", dependencies=["receipt"], artifact="submission"),
    ])
    plan = build_plan(graph, profile(weekly_hours=7, received_events=[event]))
    rows = tasks_by_id(plan)
    assert rows["request"].week_allocations == pytest.approx({"2026-10-19": 7})
    assert rows["receipt"].status == "completed"
    assert rows["submit"].week_allocations == pytest.approx({"2026-10-26": 1})
    assert plan.next_action == "request"


def test_completed_receipt_with_unscheduled_predecessor_blocks_downstream_release():
    event = "research/references_received/min=1/by=recommender/before_submit=true"
    graph = context([opportunity()], [
        task("request"),
        task("receipt", low=0, high=0, dependencies=["request"], waiting=event),
        task("submit", dependencies=["receipt"], artifact="submission"),
    ])
    plan = build_plan(graph, profile(weekly_hours=0, received_events=[event]))
    assert tasks_by_id(plan)["receipt"].status == "completed"
    assert tasks_by_id(plan)["submit"].status == "blocked"
    assert not tasks_by_id(plan)["submit"].week_allocations


def test_completion_survives_deadline_change_even_without_impact_object():
    original = opportunity()
    graph = context([original], [task("final", facts=["documents", "application_deadline"])])
    previous = build_plan(graph, profile(completed_task_ids=["final"]))
    updated = deepcopy(graph)
    updated.opportunities[0].facts[0] = fact("application_deadline", "2026-12-12T23:59:00+05:30", version="deadline-v2")
    updated.fact_versions["research/application_deadline"] = "deadline-v2"
    revised = build_plan(updated, previous.profile, previous=previous)
    assert tasks_by_id(revised)["final"].status == "completed"


def test_declared_open_call_without_sourced_portal_fragment_cannot_certify():
    target = opportunity()
    target.facts[1].excerpt = ""
    plan = build_plan(context([target], [task("prep")]), profile())
    assert plan.targets[0].schedule_status == "cannot_certify"
    assert plan.targets[0].readiness == "needs_review"


def test_shortened_deadline_recomputes_partial_effort_and_preserves_unrelated_completion():
    original = opportunity()
    other = opportunity("other")
    graph = context([original, other], [
        task("shared", targets=["research", "other"], category="Shared"),
        task("a", low=0.25, high=6, dependencies=["shared"], facts=["application_deadline"]),
        task("b", targets=["other"], dependencies=["shared"], facts=["documents"]),
    ])
    previous = build_plan(graph, profile(weekly_hours=7, completed_task_ids=["shared", "b"]))
    updated = deepcopy(graph)
    updated.opportunities[0].facts[0] = fact("application_deadline", "2026-10-20T00:00:00+05:30", version="deadline-v2")
    updated.fact_versions["research/application_deadline"] = "deadline-v2"
    impact = ChangeImpact(semantic_change=True, affected_target_ids=["research"], affected_task_ids=["a"], changes=[FactChange(opportunity_id="research", fact_name="application_deadline", old_value="2026-12-14T23:59:00+05:30", new_value="2026-10-20T00:00:00+05:30")])
    revised = build_plan(updated, previous.profile, previous=previous, impact=impact)
    rows = tasks_by_id(revised)
    assert rows["shared"].status == rows["b"].status == "completed"
    assert rows["a"].status == "unscheduled"
    assert sum(rows["a"].week_allocations.values()) <= 1 + 1e-8
    assert next(target for target in revised.targets if target.target_id == "research").schedule_status == "at_risk"


def test_non_monday_start_respects_calendar_exam_without_false_capacity_proof():
    state = ProfileState(degree="BTech", start_date="2026-10-21", horizon_weeks=2, weekly_hours=7, exam_weeks=["2026-10-26"])
    graph = context([opportunity(deadline="2026-10-26T00:00:00+05:30")], [task("prep", low=6, high=6)])
    plan = build_plan(graph, state)
    assert plan.targets[0].schedule_status == "at_risk"
    assert not any("Proven combined" in warning for warning in plan.warnings)
    assert sum(plan.weekly_used.values()) == pytest.approx(5)


def test_user_profile_is_supported_and_default_unknowns_are_not_filled():
    state = ProfileState(start_date="2026-10-19", exam_weeks=[])
    plan = build_plan(context([opportunity()], [task("prep")]), state)
    assert state.degree is None and state.year is None and not state.synthetic
    assert plan.targets[0].eligibility == "needs_review"
    assert not any("Synthetic test profile" in warning for warning in plan.warnings)
    assert any("self-reported" in warning for warning in plan.warnings)


def test_next_action_does_not_skip_unfinished_ancestor_of_observed_receipt():
    event = "research/references_received/min=1/by=recommender/before_submit=true"
    graph = context([opportunity()], [
        task("z-request", low=1, high=1),
        task("receipt", low=0, high=0, dependencies=["z-request"], waiting=event),
        task("a-submit", dependencies=["receipt"], artifact="submission"),
    ])
    plan = build_plan(graph, profile(weekly_hours=7, received_events=[event]))
    assert plan.next_action == "z-request"


def test_explicit_completion_uncheck_overrides_previous_completed_task():
    graph = context([opportunity()], [
        task("shared/cv-base/v1", targets=(), category="Shared"),
        task("statement", dependencies=["shared/cv-base/v1"], facts=["documents"]),
    ])
    previous = build_plan(graph, profile(completed_task_ids=["shared/cv-base/v1", "statement"]))
    unchecked = previous.profile.model_copy(deep=True)
    unchecked.completed_task_ids = ["shared/cv-base/v1"]
    updated = build_plan(graph, unchecked, previous=previous)
    rows = tasks_by_id(updated)
    assert rows["statement"].status == "scheduled"
    assert rows["statement"].week_allocations
    assert rows["shared/cv-base/v1"].status == "completed"
    assert updated.profile.completed_task_ids == ["shared/cv-base/v1"]
    assert previous.profile.completed_task_ids == ["shared/cv-base/v1", "statement"]
    # The normalized next state keeps the uncheck across an additional replan.
    again = build_plan(graph, updated.profile, previous=updated)
    assert tasks_by_id(again)["statement"].status == "scheduled"


def test_explicit_empty_completion_list_unchecks_completed_shared_work():
    graph = context([opportunity()], [task("shared", targets=["research"], category="Shared")])
    previous = build_plan(graph, profile(completed_task_ids=["shared"]))
    updated = build_plan(graph, profile(completed_task_ids=[]), previous=previous)
    assert tasks_by_id(updated)["shared"].status == "scheduled"
    assert updated.profile.completed_task_ids == []


def test_omitted_completion_field_inherits_previous_normalized_shared_completion():
    graph = context([opportunity()], [
        task("shared", targets=["research"], category="Shared"),
        task("final", dependencies=["shared"], facts=["documents"]),
    ])
    previous = build_plan(graph, profile(completed_task_ids=["shared"]))
    changed_availability = profile(weekly_hours=3)
    assert "completed_task_ids" not in changed_availability.model_fields_set
    updated = build_plan(graph, changed_availability, previous=previous)
    assert tasks_by_id(updated)["shared"].status == "completed"
    assert updated.profile.completed_task_ids == ["shared"]


def test_incompatible_completion_cannot_resurrect_after_two_noop_replans():
    graph = context([opportunity(extras=[fact("statement_max_words", 400)])], [
        task("shared", targets=["research"], category="Shared"),
        task("statement", dependencies=["shared"], facts=["statement_max_words"]),
    ])
    previous = build_plan(graph, profile(completed_task_ids=["shared", "statement"]))
    changed = deepcopy(graph)
    changed.opportunities[0].facts[-1] = fact("statement_max_words", 300, version="statement-limit-v2")
    changed.fact_versions["research/statement_max_words"] = "statement-limit-v2"
    impact = ChangeImpact(
        semantic_change=True, affected_target_ids=["research"], affected_task_ids=["statement"],
        changes=[FactChange(opportunity_id="research", fact_name="statement_max_words", old_value=400, new_value=300)],
    )
    invalidated = build_plan(changed, previous.profile, previous=previous, impact=impact)
    assert tasks_by_id(invalidated)["statement"].status == "scheduled"
    assert invalidated.profile.completed_task_ids == ["shared"]
    assert previous.profile.completed_task_ids == ["shared", "statement"]
    first_noop = build_plan(changed, invalidated.profile, previous=invalidated, impact=ChangeImpact())
    second_noop = build_plan(changed, first_noop.profile, previous=first_noop, impact=ChangeImpact())
    for plan in (first_noop, second_noop):
        assert tasks_by_id(plan)["statement"].status == "scheduled"
        assert tasks_by_id(plan)["shared"].status == "completed"
        assert plan.profile.completed_task_ids == ["shared"]
        assert tasks_by_id(plan)["statement"].week_allocations
    # A later explicit completion claim represents newly reported compatible work.
    redone_state = second_noop.profile.model_copy(deep=True)
    redone_state.completed_task_ids.append("statement")
    redone = build_plan(changed, redone_state, previous=second_noop)
    assert tasks_by_id(redone)["statement"].status == "completed"
    assert redone.profile.completed_task_ids == ["shared", "statement"]


def test_missing_or_unverified_completion_claims_are_removed_from_returned_profile():
    event = "research/reference_received"
    graph = context([opportunity()], [task("receipt", low=0, high=0, waiting=event)])
    state = profile(completed_task_ids=["missing", "receipt"])
    plan = build_plan(graph, state)
    assert plan.profile.completed_task_ids == []
    assert state.completed_task_ids == ["missing", "receipt"]
    assert tasks_by_id(plan)["receipt"].status == "waiting"


def test_graph_requirement_membership_guard_is_retained_without_official_criterion():
    graph = context([opportunity(), opportunity("other")], [
        task("research-prep", facts=["documents"]),
        task("other-prep", targets=["other"], facts=["documents"]),
    ])
    graph.fact_versions["research/requirement_set"] = "research-membership-v1"
    graph.fact_versions["other/requirement_set"] = "other-membership-v1"
    plan = build_plan(graph, profile())
    targets = {target.target_id: target for target in plan.targets}
    assert "research-membership-v1" in targets["research"].used_fact_versions
    assert "other-membership-v1" not in targets["research"].used_fact_versions
    assert plan.fact_versions["research/requirement_set"] == "research-membership-v1"
    assert plan.fact_versions["other/requirement_set"] == "other-membership-v1"
    assert all(criterion.name != "requirement_set" for target in plan.targets for criterion in target.criteria)
    assert all("research-membership-v1" not in task.fact_version_ids for task in plan.tasks)


@pytest.mark.parametrize("degree", ["BTech", "B. Tech", "BE", "B.E."])
def test_mitacs_degree_program_type_matches_without_false_cs_discipline_rejection(degree):
    target_id = "mitacs-summer-2027"
    target = opportunity(target_id, extras=[
        fact("degree_program_types", ["be", "btech"], target=target_id),
        fact("fields", None, target=target_id, status="unknown", kind="information"),
        fact("participating_institution", None, target=target_id, status="unknown"),
    ])
    graph = context([target], [task("prep", targets=[target_id])])
    plan = build_plan(graph, profile(degree=degree, field="computer_science"))
    criteria = {criterion.name: criterion for criterion in plan.targets[0].criteria}
    assert criteria["degree_program_types"].status == "met"
    assert "fields" not in criteria
    assert criteria["participating_institution"].status == "unknown"
    assert plan.targets[0].eligibility == "needs_review"
    assert plan.targets[0].schedule_status == "cannot_certify"


def test_degree_program_type_does_not_infer_equivalence_from_generic_degree_level():
    graph = context([opportunity(extras=[fact("degree_program_types", ["be", "btech"])])], [task("prep")])
    plan = build_plan(graph, profile(degree="bachelor", field="computer_science"))
    criterion = next(item for item in plan.targets[0].criteria if item.name == "degree_program_types")
    assert criterion.status == "unknown"
    assert plan.targets[0].eligibility == "needs_review"


def test_known_exact_degree_program_mismatch_is_not_met():
    graph = context([opportunity(extras=[fact("degree_program_types", ["be"])])], [task("prep")])
    plan = build_plan(graph, profile(degree="BTech"))
    criterion = next(item for item in plan.targets[0].criteria if item.name == "degree_program_types")
    assert criterion.status == "not_met"
    assert plan.targets[0].eligibility == "not_eligible"
