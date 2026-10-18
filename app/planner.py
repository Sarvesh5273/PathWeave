"""Deterministic allocation of the prerequisite closure supplied by FalkorDB.

The graph owns which work is required and which artifacts are compatible. This
module validates that closure, assesses a small typed criterion vocabulary, and
allocates conservative effort estimates against one calendar. It never discovers
requirements or infers receipt of a third-party document from elapsed time.

Since v0.7 it also orders the graph's reviewed learning topics by prerequisite
into a self-reported roadmap and honors per-day availability patterns, exam
weeks and holiday dates. Topics, prerequisites and resources are team-authored
guidance; ratings are self-reports, never assessed knowledge.
"""

from __future__ import annotations

import heapq
import math
import re
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.models import (
    ChangeImpact,
    CriterionResult,
    Fact,
    GraphContext,
    Opportunity,
    Plan,
    PlanTask,
    PreparationTask,
    ProfileState,
    RoadmapTopic,
    TargetAssessment,
)

IST = ZoneInfo("Asia/Kolkata")
EPSILON = 1e-8
ELIGIBILITY_FIELDS = {
    "degree_levels", "degree_program_types", "fields", "min_study_year", "min_years_remaining",
    "max_years_remaining", "year_constraint", "institution_approval",
}
DELIVERABLE_FIELDS = {
    "documents", "reference_min", "reference_received_before_submit",
    "reference_submitter", "reference_forbidden", "statement_max_words",
    "statement_max_chars", "statement_max_pages", "document_format", "transcript_translation",
}
CALL_FIELDS = {"application_deadline", "portal_status"}


def _unique(items):
    return list(dict.fromkeys(items))


def _aware(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(IST)


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _token(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _degree(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _token(value)
    if normalized in {"bachelor", "bachelors", "btech", "be", "bs", "bsc", "ba", "undergraduate"}:
        return "bachelor"
    if normalized in {"master", "masters", "mtech", "me", "ms", "msc", "ma", "graduate"}:
        return "master"
    if normalized in {"phd", "doctoral", "doctorate"}:
        return "phd"
    return normalized


def _field(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _token(value)
    return {"cs": "computerscience", "cse": "computerscience", "ee": "electricalengineering"}.get(normalized, normalized)


def _version(context: GraphContext, target_id: str, fact: Fact) -> str:
    return context.fact_versions.get(f"{target_id}/{fact.name}", fact.version_id)


def _valid_fact(fact: Fact, opportunity: Opportunity) -> bool:
    return (
        fact.status == "known" and bool(fact.excerpt.strip())
        and bool(fact.source_url or opportunity.source_url)
    )


def _year_status(value: Any, profile: ProfileState) -> tuple[str, str]:
    if not isinstance(value, dict) or not isinstance(value.get("type"), str) or value.get("type") not in {"penultimate", "final_two_years"}:
        return "unknown", "The sourced year condition is outside the supported typed vocabulary."
    degree = _degree(profile.degree)
    applies = value.get("applies_to")
    if not isinstance(applies, list) or not all(isinstance(item, str) for item in applies):
        return "unknown", "The source does not identify the degrees to which the year condition applies."
    if degree is None:
        return "unknown", "Supply the current degree level to check this condition."
    if degree not in {_degree(item) for item in applies}:
        return "met", "The sourced year condition does not apply to this degree level."
    if profile.year is None or profile.total_years is None:
        return "unknown", "Supply current study year and total program length."
    if profile.total_years <= 0 or not 1 <= profile.year <= profile.total_years:
        return "unknown", "Current study year and program length are inconsistent."
    assessment_time = value.get("assessed_at")
    if not isinstance(assessment_time, str) or assessment_time not in {"application", "application_or_internship_start", "internship_start"}:
        return "unknown", "The source does not establish when the year condition is assessed."
    if assessment_time == "internship_start":
        return "unknown", "Study-year status at the future internship start has not been supplied."
    matches = (
        profile.year == profile.total_years - 1 if value["type"] == "penultimate"
        else profile.year >= max(1, profile.total_years - 1)
    )
    if not matches and assessment_time == "application_or_internship_start":
        return "unknown", "Current study year does not qualify; status at internship start needs review."
    return (
        "met" if matches else "not_met",
        f"Current year {profile.year} of {profile.total_years} {'meets' if matches else 'does not meet'} the sourced {value['type'].replace('_', ' ')} condition.",
    )


def _eligibility(fact: Fact, profile: ProfileState, opportunity: Opportunity) -> tuple[str, str]:
    value = fact.value
    if fact.name == "degree_program_types":
        # Degree program labels are exact source vocabulary. Do not collapse
        # BE/BTech to bachelor or compare them to a discipline such as CS.
        if not isinstance(value, list) or not value or not all(isinstance(item, str) and _token(item) in {"be", "btech"} for item in value):
            return "unknown", "The permitted degree program types are outside the supported BE/BTech vocabulary."
        if profile.degree is None or _token(profile.degree) not in {"be", "btech"}:
            return "unknown", "Supply the exact degree program label to check the sourced BE/BTech condition."
        matches = _token(profile.degree) in {_token(item) for item in value}
        return "met" if matches else "not_met", f"Self-reported degree program {profile.degree} {'matches' if matches else 'does not match'} the sourced degree program types."
    if fact.name == "degree_levels":
        if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
            return "unknown", "The permitted degree levels are not a supported nonempty list."
        if profile.degree is None:
            return "unknown", "Supply the current degree level."
        matches = _degree(profile.degree) in {_degree(item) for item in value}
        return "met" if matches else "not_met", f"Self-reported degree {profile.degree} {'matches' if matches else 'does not match'} the sourced degree levels."
    if fact.name == "fields":
        if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
            return "unknown", "The permitted study fields are not a supported nonempty list."
        if profile.field is None:
            return "unknown", "Supply the current study field."
        # Related-field wording is deliberately not treated as exact membership.
        accepted = {_field(item) for item in value}
        if _field(profile.field) in accepted:
            return "met", f"Self-reported field {profile.field} matches a sourced field."
        exception = next((item for item in opportunity.facts if item.name == "field_evidence_exception"), None)
        if any("related" in item.casefold() for item in value) or (exception and _valid_fact(exception, opportunity) and exception.value is True):
            return "unknown", "Related-field eligibility requires human review."
        return "not_met", f"Self-reported field {profile.field} does not match the sourced fields."
    if fact.name == "year_constraint":
        return _year_status(value, profile)
    if fact.name in {"min_study_year", "min_years_remaining", "max_years_remaining"}:
        if not _number(value) or value < 0:
            return "unknown", "The study-year threshold is missing or malformed."
        if fact.name == "min_study_year":
            reported = profile.year
        elif profile.year is None or profile.total_years is None or not 1 <= profile.year <= profile.total_years:
            reported = None
        else:
            reported = profile.total_years - profile.year
        if reported is None:
            return "unknown", "Supply consistent current study year and total program length."
        matches = reported <= value if fact.name == "max_years_remaining" else reported >= value
        return "met" if matches else "not_met", f"Self-reported study state {reported} {'meets' if matches else 'does not meet'} the sourced threshold {value:g}."
    if fact.name == "institution_approval":
        if not isinstance(value, bool):
            return "unknown", "Institution approval condition has no supported boolean value."
        if value is False:
            return "met", "The sourced condition does not require institution approval."
        if f"{opportunity.id}/institution_approval_confirmed" in profile.received_events:
            return "met", "Home-institution approval is recorded by the user; it has not been independently verified."
        return "unknown", "Home-institution approval has not been observed; being listed is a separate condition."
    return "unknown", "The profile has no verified input for this sourced requirement; human review is needed."


def _deliverable(fact: Fact) -> tuple[str, str]:
    value = fact.value
    if fact.name == "documents":
        supported = isinstance(value, list) and all(isinstance(item, str) for item in value)
    elif fact.name in {"reference_min", "statement_max_words", "statement_max_chars", "statement_max_pages"}:
        supported = _number(value) and value >= 0 and (fact.name != "reference_min" or isinstance(value, int))
    elif fact.name in {"reference_received_before_submit", "reference_forbidden"}:
        supported = isinstance(value, bool)
    elif fact.name == "reference_submitter":
        supported = isinstance(value, str) and bool(value.strip()) and value.casefold() != "unknown"
    elif fact.name == "document_format":
        supported = isinstance(value, str) and value.casefold() in {"pdf", "docx", "txt"}
    else:
        supported = isinstance(value, str) and value in {"self", "english_explanation", "notarized"}
    if not supported:
        return "unknown", "The sourced deliverable condition needs review before readiness can be certified."
    return "information", "Sourced deliverable condition; preparation and completion are checked through the graph recipe."


def _assess(context: GraphContext, opportunity: Opportunity, profile: ProfileState) -> TargetAssessment:
    criteria = []
    used = []
    known_eligibility = 0
    hard_failure = False
    needs_review = False
    for fact in opportunity.facts:
        relevant = fact.name in ELIGIBILITY_FIELDS | DELIVERABLE_FIELDS | CALL_FIELDS
        if fact.kind == "preference":
            status = "preference"
            explanation = "Source preference only; this does not exclude the applicant."
            if fact.name == "work_authorization_preference":
                explanation += f" Self-reported Singapore work authorization: {profile.right_to_work_singapore}."
            if fact.status != "known":
                explanation += " Its current source value is unverified."
        elif fact.name in ELIGIBILITY_FIELDS and fact.kind == "requirement":
            known_eligibility += 1
            if _valid_fact(fact, opportunity):
                status, explanation = _eligibility(fact, profile, opportunity)
            else:
                status, explanation = "unknown", "This eligibility condition is missing, conflicting, or lacks a source fragment."
            hard_failure |= status == "not_met"
            needs_review |= status == "unknown"
        elif fact.name in DELIVERABLE_FIELDS and fact.kind == "requirement":
            status, explanation = _deliverable(fact) if _valid_fact(fact, opportunity) else ("unknown", "This deliverable condition is unverified or conflicting.")
            needs_review |= status == "unknown"
        elif fact.name in CALL_FIELDS:
            if fact.name == "application_deadline":
                status = "information" if _valid_fact(fact, opportunity) and _aware(fact.value) else "unknown"
                explanation = "Sourced application cutoff, with timezone." if status == "information" else "No supported timezone-aware application cutoff; scheduling cannot certify the deadline."
            else:
                status = "information" if _valid_fact(fact, opportunity) and isinstance(fact.value, str) and fact.value in {"open", "closed", "future"} else "unknown"
                explanation = "Sourced portal state is checked independently of the deadline." if status == "information" else "Current application portal state is unverified."
        elif fact.kind == "requirement":
            status = "unknown"
            explanation = "This sourced requirement is outside the supported assessment vocabulary; review it with the source."
            needs_review = True
        elif relevant and fact.status == "conflicting":
            status = "unknown"
            explanation = "Relevant source evidence conflicts; human review is required."
            needs_review = True
        else:
            # Fee/funding metadata and unknown placeholders do not drive a decision.
            continue
        version = _version(context, opportunity.id, fact)
        if version:
            used.append(version)
        if fact.name == "fields" and status == "unknown":
            exception = next((item for item in opportunity.facts if item.name == "field_evidence_exception"), None)
            if exception and _valid_fact(exception, opportunity) and exception.value is True:
                exception_version = _version(context, opportunity.id, exception)
                if exception_version:
                    used.append(exception_version)
        criteria.append(CriterionResult(
            name=fact.name, status=status, explanation=explanation,
            fact_version_id=version, source_url=fact.source_url or opportunity.source_url,
            excerpt=fact.excerpt,
        ))
    if opportunity.verification == "uncertain":
        needs_review = True
    eligibility = "not_eligible" if hard_failure else "conditions_met" if known_eligibility and not needs_review else "needs_review"
    reasons = []
    if not known_eligibility:
        reasons.append("No supported hard eligibility conditions have been established.")
    if opportunity.verification == "uncertain":
        reasons.append("The source is marked uncertain; retained facts cannot certify current readiness.")
    reasons.extend(criterion.explanation for criterion in criteria if criterion.status in {"not_met", "unknown"} and criterion.name not in CALL_FIELDS)
    return TargetAssessment(
        target_id=opportunity.id, eligibility=eligibility, call_status=opportunity.call_status,
        criteria=criteria, used_fact_versions=_unique(used), reasons=_unique(reasons),
    )


def _same_recipe(old: PlanTask, task: PreparationTask, versions: list[str], impact: ChangeImpact | None, context: GraphContext, previous: Plan) -> bool:
    # Changed hours/deadlines affect planning estimates, not work already done.
    same = (
        old.task_id == task.id and old.title == task.title and old.category == task.category
        and set(old.dependencies) == set(task.dependencies) and old.waiting_for == task.waiting_for
    )
    if not same:
        return False
    if task.category == "Shared" and not task.fact_names:
        return True
    if set(old.target_ids) != set(task.target_ids):
        return False
    if impact:
        relevant_change = any(
            change.opportunity_id in task.target_ids and change.fact_name in task.fact_names
            and change.fact_name not in CALL_FIELDS for change in impact.changes
        )
        if relevant_change:
            return False
    if set(old.fact_version_ids) == set(versions):
        return True
    # A deadline or portal-state change cannot invalidate an actual document.
    relevant_keys = [f"{target_id}/{name}" for target_id in task.target_ids for name in task.fact_names if name not in CALL_FIELDS]
    if all(previous.fact_versions.get(key) == context.fact_versions.get(key) for key in relevant_keys):
        return True
    return False


def _roadmap(context: GraphContext, profile: ProfileState, plan_tasks: dict[str, PlanTask],
             tasks: dict[str, PreparationTask]) -> list[RoadmapTopic]:
    """Order the graph's reviewed topics by prerequisites with self-reported status.

    Ordering is dependency-first and stable; topics without a scheduled shared
    foundation task are shown as prerequisite guidance only. Ratings never remove
    required work; they only explain where to start and how to review.
    """
    topics = {topic.key: topic for topic in context.topics}
    if not topics:
        return []
    ratings = profile.skill_ratings
    degree = {key: sum(1 for prerequisite in topic.prerequisites if prerequisite in topics)
              for key, topic in topics.items()}
    children: dict[str, list[str]] = defaultdict(list)
    for key, topic in topics.items():
        for prerequisite in topic.prerequisites:
            if prerequisite in topics:
                children[prerequisite].append(key)
    ready = sorted(key for key, value in degree.items() if value == 0)
    order_keys: list[str] = []
    while ready:
        key = ready.pop(0)
        order_keys.append(key)
        for child in sorted(children[key]):
            degree[child] -= 1
            if degree[child] == 0:
                ready.append(child)
                ready.sort()
    order_keys.extend(sorted(set(topics) - set(order_keys)))
    status_rank = {"completed": 0, "scheduled": 1, "waiting": 2, "blocked": 3, "unscheduled": 4}
    entries: list[RoadmapTopic] = []
    start_assigned = False
    for index, key in enumerate(order_keys):
        topic = topics[key]
        foundation = f"shared/skill-{key}-foundation/v1"
        task_ids = [foundation] if foundation in tasks else []
        statuses = [plan_tasks[task_id].status for task_id in task_ids if task_id in plan_tasks]
        task_status = min(statuses, key=lambda status: status_rank.get(status, 5)) if statuses else ""
        rating = ratings.get(key, "")
        start_here = False
        if task_ids and not start_assigned and rating != "comfortable":
            start_here, start_assigned = True, True
        note = ""
        if not task_ids:
            note = "Prerequisite knowledge for a required topic; it is not part of the scheduled required work."
        elif rating == "comfortable":
            note = "You marked this comfortable; the scheduled practice stays available for review."
        entries.append(RoadmapTopic(
            key=key, title=topic.title or key, family=topic.family, order=index + 1,
            rating=rating, start_here=start_here, prerequisites=list(topic.prerequisites),
            resources=[dict(item) for item in topic.resources],
            task_ids=task_ids, task_status=task_status,
            required_by={key: list(names) for key, names in topic.required_by.items()},
            scheduled=task_status in {"completed", "scheduled", "waiting"}, note=note,
        ))
    return entries


def build_plan(
    context: GraphContext,
    profile: ProfileState,
    previous: Plan | None = None,
    impact: ChangeImpact | None = None,
) -> Plan:
    """Build a proposal without mutating the graph, profile, or earlier plan.

    Weekly availability follows the profile's per-day pattern when supplied and
    is otherwise spread evenly across seven calendar days; exam weeks and holiday
    dates are protected. The internal time line preserves within-week precedence;
    returned week totals are its projection. A mathematical infeasibility
    certificate uses an optimistic capacity bound, never the conservative
    spreading assumption or a greedy allocation failure.
    """
    warnings = [
        "Effort ranges are team-authored estimates. The schedule uses their upper bounds and does not predict selection.",
        "Profile inputs and progress are self-reported; they are not independent eligibility or skill verification.",
    ]
    if profile.weekly_pattern:
        warnings.append("Weekly availability follows your per-day pattern; exam weeks and holidays are protected.")
    else:
        warnings.append("Weekly availability is assumed to be spread evenly across seven calendar days; midweek deadline capacity is prorated.")
    if context.topics:
        warnings.append("The learning roadmap orders authored practice topics by prerequisites; it is study guidance, not a syllabus, requirement or skill assessment.")
    if profile.synthetic:
        warnings.append("Synthetic test profile; this plan does not describe a real applicant.")
    try:
        first_date = date.fromisoformat(profile.start_date)
    except ValueError as exc:
        raise ValueError("start_date must be an ISO calendar date") from exc
    start = datetime.combine(first_date, time.min, IST)
    end = start + timedelta(weeks=profile.horizon_weeks)
    selected_ids = _unique(opportunity.id for opportunity in context.opportunities)
    opportunities = {opportunity.id: opportunity for opportunity in context.opportunities}
    if any(f.name == "requirements_review" and f.status != "known"
           for opportunity in opportunities.values() for f in opportunity.facts):
        warnings.append("Source requirement review is incomplete; supported preparation tasks are retained, but remaining conditions need review.")
    if len(selected_ids) > 3:
        raise ValueError("Select at most three internship targets")
    if len(opportunities) != len(context.opportunities):
        raise ValueError("Opportunity IDs must be unique within a graph context")
    assessments = {key: _assess(context, opportunity, profile) for key, opportunity in opportunities.items()}
    exam_dates = set()
    invalid_exam = False
    for value in profile.exam_weeks:
        try:
            parsed = date.fromisoformat(value)
            if parsed.weekday() != 0:
                raise ValueError("not Monday")
            exam_dates.add(parsed)
        except ValueError:
            invalid_exam = True
            warnings.append(f"Exam blackout '{value}' is not an ISO Monday; availability cannot be certified.")
    holiday_dates = set()
    for value in profile.holidays:
        try:
            holiday_dates.add(date.fromisoformat(value))
        except (ValueError, TypeError):
            warnings.append(f"Holiday '{value}' is not an ISO calendar date; it was ignored for scheduling.")
    pattern = {int(key): value for key, value in profile.weekly_pattern.items()
               if key in {"0", "1", "2", "3", "4", "5", "6"}}
    # The infeasibility certificate credits every touched week a full weekly
    # pattern total, even when only part of the week precedes the cutoff and an
    # exam day inside it is protected. The bound stays deliberately generous.
    week_total = sum(pattern.values()) if pattern else profile.weekly_hours
    slots = []
    weekly_capacity: dict[str, float] = {}
    for index in range(profile.horizon_weeks * 7):
        day_start = start + timedelta(days=index)
        day_end = day_start + timedelta(days=1)
        key = (first_date + timedelta(weeks=index // 7)).isoformat()
        monday = day_start.date() - timedelta(days=day_start.weekday())
        day_hours = pattern.get(day_start.weekday(), 0.0) if pattern else profile.weekly_hours / 7
        hours = 0.0 if invalid_exam or monday in exam_dates or day_start.date() in holiday_dates else day_hours
        weekly_capacity[key] = weekly_capacity.get(key, 0.0) + hours
        slots.append({"start": day_start, "end": day_end, "week": key, "hours": hours, "used": 0.0, "cursor": day_start})
    available_hours = sum(weekly_capacity.values())

    deadlines: dict[str, datetime | None] = {}
    modes = {}
    for target_id, opportunity in opportunities.items():
        facts = {fact.name: fact for fact in opportunity.facts}
        deadline_fact = facts.get("application_deadline")
        deadline = _aware(deadline_fact.value) if deadline_fact and _valid_fact(deadline_fact, opportunity) else None
        deadlines[target_id] = deadline
        portal_fact = facts.get("portal_status")
        portal_supported = bool(portal_fact and _valid_fact(portal_fact, opportunity) and isinstance(portal_fact.value, str) and portal_fact.value in {"open", "closed", "future"})
        source_state = portal_fact.value if portal_supported else opportunity.call_status
        if deadline and deadline <= start:
            mode = "excluded"
            assessments[target_id].reasons.append("The sourced application deadline is before this planning period.")
        elif source_state == "closed" and not (deadline and deadline > start):
            mode = "excluded"
            assessments[target_id].reasons.append("The source reports a closed call without a supported upcoming cutoff.")
        elif source_state in {"future", "closed"}:
            mode = "preparation"
            assessments[target_id].reasons.append("Preparation only: the source does not confirm an open application portal.")
        elif source_state == "open" and portal_supported:
            mode = "current"
        else:
            mode = "unknown"
            assessments[target_id].reasons.append("Application portal state is unknown; confirm it before submitting.")
        if assessments[target_id].eligibility == "not_eligible":
            mode = "excluded"
        modes[target_id] = mode
        assessments[target_id].call_status = str(source_state)

    tasks: dict[str, PreparationTask] = {}
    collisions = set()
    for task in context.tasks:
        if task.id not in tasks:
            tasks[task.id] = task.model_copy(deep=True)
            continue
        current = tasks[task.id]
        current.target_ids = _unique(current.target_ids + task.target_ids)
        signature_fields = {"title", "category", "hours_low", "hours_high", "dependencies", "waiting_for", "artifact_type", "provenance", "fact_names"}
        if any(getattr(current, field) != getattr(task, field) for field in signature_fields):
            collisions.add(task.id)
        else:
            dates = [value for value in (_aware(current.due_at), _aware(task.due_at)) if value]
            current.due_at = min(dates).isoformat() if dates else None
    children = defaultdict(list)
    degree = {}
    invalid = {}
    for task_id, task in tasks.items():
        missing = [dep for dep in task.dependencies if dep not in tasks]
        if missing:
            invalid[task_id] = f"Graph prerequisite closure is incomplete: {', '.join(missing)}."
        if task_id in collisions:
            invalid[task_id] = "The graph returned incompatible recipes with the same task ID."
        if not (_number(task.hours_low) and _number(task.hours_high) and 0 <= task.hours_low <= task.hours_high):
            invalid[task_id] = "The graph recipe has an invalid effort range."
        degree[task_id] = len(set(dep for dep in task.dependencies if dep in tasks))
        for dependency in set(task.dependencies):
            if dependency in tasks:
                children[dependency].append(task_id)
    queue = [task_id for task_id, value in degree.items() if value == 0]
    heapq.heapify(queue)
    order = []
    while queue:
        task_id = heapq.heappop(queue)
        order.append(task_id)
        for child in children[task_id]:
            degree[child] -= 1
            if degree[child] == 0:
                heapq.heappush(queue, child)
    for task_id in set(tasks) - set(order):
        invalid[task_id] = "The graph recipe contains a dependency cycle or depends on a cycle."
    order.extend(sorted(set(tasks) - set(order)))

    # Reverse the already-returned dependency DAG to propagate deadline and target
    # metadata. No source-to-domain relationships are reconstructed here.
    target_links = {task_id: set(task.target_ids) & set(selected_ids) for task_id, task in tasks.items()}
    # Shared deadlines are derived from the active target closure. The graph may
    # also contain an expired selected target; its cutoff cannot govern active work.
    task_deadlines = {task_id: None if task.category == "Shared" else _aware(task.due_at) for task_id, task in tasks.items()}
    for task_id in reversed(order):
        task = tasks[task_id]
        candidates = [deadlines[target_id] for target_id in target_links[task_id] if modes[target_id] != "excluded" and deadlines[target_id]]
        if candidates:
            task_deadlines[task_id] = min(candidates + ([task_deadlines[task_id]] if task_deadlines[task_id] else []))
        for dependency in task.dependencies:
            if dependency in tasks:
                target_links[dependency].update(target_links[task_id])
                candidate = task_deadlines[task_id]
                if candidate and any(modes[target_id] != "excluded" for target_id in target_links[task_id]):
                    task_deadlines[dependency] = min(candidate, task_deadlines[dependency]) if task_deadlines[dependency] else candidate
    for task_id in order:
        for dependency in tasks[task_id].dependencies:
            if dependency in invalid and task_id not in invalid:
                invalid[task_id] = f"A prerequisite is invalid: {dependency}."
        unknown_links = set(tasks[task_id].target_ids) - set(selected_ids)
        if unknown_links:
            invalid[task_id] = "Task links to an opportunity outside the selected graph context."
    warnings.extend(f"{task_id}: {reason}" for task_id, reason in sorted(invalid.items()))

    old_tasks = {task.task_id: task for task in previous.tasks} if previous and previous.profile.id == profile.id else {}
    # A supplied list is the caller's complete current state, including an
    # explicit empty list when work is unchecked. Omitted state may inherit the
    # prior normalized profile, never a PlanTask status that the caller revoked.
    completion_ids_supplied = "completed_task_ids" in profile.model_fields_set
    completion_claims = (
        profile.completed_task_ids if completion_ids_supplied or not old_tasks
        else previous.profile.completed_task_ids
    )
    # Recommended study completion is validated separately, never against
    # source recipes or employer requirements.
    completion_claims = [value for value in completion_claims if not value.startswith("study/")]
    explicitly_completed = set(completion_claims)
    observed_events = set(profile.received_events)
    plan_tasks = {}
    retained = set()
    for task_id, task in tasks.items():
        versions = _unique(
            _version(context, target_id, fact)
            for target_id in task.target_ids if target_id in opportunities
            for fact in opportunities[target_id].facts if fact.name in task.fact_names
            if _version(context, target_id, fact)
        )
        result = PlanTask(
            task_id=task_id, title=task.title, category=task.category,
            target_ids=sorted(target_links[task_id]), dependencies=_unique(task.dependencies),
            waiting_for=task.waiting_for, hours_low=task.hours_low, hours_high=task.hours_high,
            fact_version_ids=versions,
        )
        active = any(modes[target_id] != "excluded" for target_id in target_links[task_id])
        old = old_tasks.get(task_id)
        compatible_old = bool(old and _same_recipe(old, task, versions, impact, context, previous))
        completion_requested = task_id in explicitly_completed
        if task_id in invalid:
            result.status, result.reason = "blocked", invalid[task_id]
        elif not active:
            result.reason = "No active or future preparation target requires this task."
        elif task.waiting_for and task.waiting_for not in observed_events:
            result.status, result.reason = "waiting", f"Await an observed external event: {task.waiting_for}. Requesting it is not receipt."
        elif task.waiting_for and task.waiting_for in observed_events:
            result.status, result.reason = "completed", "Receipt is recorded by the user; delivery has not been independently verified."
        elif completion_requested and (not old or compatible_old):
            result.status, result.reason = "completed", "Compatible work marked complete by the user is retained from this profile or its earlier plan."
            retained.add(task_id)
        elif task.artifact_type == "submission" and all(modes[target_id] != "current" for target_id in target_links[task_id]):
            result.status, result.reason = "blocked", "Current portal opening must be confirmed before submission readiness can be released."
        elif completion_requested:
            result.reason = "The previous completion does not match the current graph recipe; review or redo this target-specific work."
        plan_tasks[task_id] = result
    missing_completions = explicitly_completed - set(tasks)
    if missing_completions:
        warnings.append("Completed IDs outside the current graph recipe are not counted: " + ", ".join(sorted(missing_completions)) + ".")

    finished: dict[str, datetime] = {}
    ready = []
    handled = set()
    pending_degree = {task_id: len(set(task.dependencies)) for task_id, task in tasks.items()}
    for task_id in tasks:
        if task_id not in handled and pending_degree[task_id] == 0:
            heapq.heappush(ready, (task_deadlines[task_id] or end, task_id))

    def allocate(task_id: str, release: datetime) -> tuple[dict[str, float], datetime | None]:
        requested = tasks[task_id].hours_high
        cutoff = min(task_deadlines[task_id] or end, end)
        if release > cutoff:
            return {}, None
        if requested <= EPSILON:
            return {}, release
        remainder = requested
        allocations = defaultdict(float)
        completion = None
        for slot in slots:
            if slot["hours"] <= EPSILON:
                continue
            left = max(slot["start"], slot["cursor"], release)
            right = min(slot["end"], cutoff)
            if left >= right:
                continue
            remaining_capacity = slot["hours"] - slot["used"]
            prorated_capacity = slot["hours"] * (right - left).total_seconds() / 86400
            capacity = min(remaining_capacity, prorated_capacity)
            if capacity <= EPSILON:
                continue
            assigned = min(remainder, capacity)
            completion = left + timedelta(seconds=assigned / slot["hours"] * 86400)
            slot["used"] += assigned
            slot["cursor"] = completion
            allocations[slot["week"]] += assigned
            remainder -= assigned
            if remainder <= EPSILON:
                return dict(allocations), completion
        return dict(allocations), None

    while ready:
        _, task_id = heapq.heappop(ready)
        if task_id in handled:
            continue
        result = plan_tasks[task_id]
        task = tasks[task_id]
        if result.status == "completed":
            if all(dependency in finished for dependency in task.dependencies):
                finished[task_id] = max([start] + [finished[dependency] for dependency in task.dependencies])
            else:
                result.reason += " Recorded completion is retained, but unresolved prerequisites prevent releasing downstream work."
        elif result.status in {"blocked", "waiting"}:
            pass
        elif not any(modes[target_id] != "excluded" for target_id in target_links[task_id]):
            pass
        elif any(dependency not in finished for dependency in task.dependencies):
            result.status, result.reason = "blocked", "A prerequisite is waiting, invalid, or has no complete allocation."
        else:
            release = max([start] + [finished[dependency] for dependency in task.dependencies if dependency in finished])
            result.week_allocations, completion = allocate(task_id, release)
            if completion is not None:
                result.status = "scheduled"
                label = "Preparation only. " if all(modes[target_id] == "preparation" for target_id in target_links[task_id]) else ""
                result.reason = label + "Upper-bound effort fits the assumed calendar after its prerequisites."
                finished[task_id] = completion
            else:
                result.status = "unscheduled"
                result.reason = "The deterministic allocator did not fit all upper-bound effort before the known cutoff or horizon; this alone is not proof of infeasibility."
        handled.add(task_id)
        for child in children[task_id]:
            pending_degree[child] -= 1
            if pending_degree[child] == 0 and child not in handled:
                heapq.heappush(ready, (task_deadlines[child] or end, child))
    for task_id in set(tasks) - handled:
        if plan_tasks[task_id].status not in {"completed", "waiting"}:
            plan_tasks[task_id].status = "blocked"
            plan_tasks[task_id].reason = invalid.get(task_id, "A prerequisite is invalid or unresolved.")

    # Full weekly budgets are an optimistic upper bound even when the equal-spread
    # allocator cannot use them before a midweek cutoff. Summed positive lower
    # estimates exceeding that bound are an actual impossibility certificate.
    def optimistic_capacity(cutoff: datetime) -> float:
        touched = set()
        wall_hours = 0.0
        for slot in slots:
            right = min(slot["end"], cutoff)
            if slot["start"] < right and slot["hours"] > EPSILON:
                touched.add(slot["week"])
                wall_hours += (right - slot["start"]).total_seconds() / 3600
        full_budget = len(touched) * week_total
        return min(full_budget, wall_hours)

    proof_tasks = set()
    active_task_ids = {
        task_id for task_id, result in plan_tasks.items()
        if result.status != "completed" and task_id not in invalid
        and any(modes[target_id] != "excluded" for target_id in target_links[task_id])
        and (tasks[task_id].artifact_type != "submission" or any(modes[target_id] == "current" for target_id in target_links[task_id]))
    }
    for cutoff in sorted({min(value, end) for task_id, value in task_deadlines.items() if value and task_id in active_task_ids}):
        due = {task_id for task_id in active_task_ids if task_deadlines[task_id] and task_deadlines[task_id] <= cutoff}
        lower = sum(tasks[task_id].hours_low for task_id in due)
        capacity = optimistic_capacity(cutoff)
        if lower > capacity + EPSILON:
            proof_tasks.update(due)
            warnings.append(f"Proven combined lower-bound shortfall: {lower:g} estimated hours due by {cutoff.isoformat()} exceed the optimistic {capacity:g}-hour shared capacity.")

    for target_id, assessment in assessments.items():
        required = [task_id for task_id in order if target_id in target_links[task_id]]
        assessment.required_task_ids = required
        target_results = [plan_tasks[task_id] for task_id in required]
        used = assessment.used_fact_versions + [version for result in target_results for version in result.fact_version_ids]
        # Do not attach another target's versions through a shared task.
        own_versions = {_version(context, target_id, fact) for fact in opportunities[target_id].facts}
        assessment.used_fact_versions = _unique(version for version in used if version in own_versions and version)
        # This graph metadata version records hard-requirement membership. It
        # protects acceptance when a previously unseen requirement is added,
        # without pretending the guard itself is an official sourced criterion.
        membership_version = context.fact_versions.get(f"{target_id}/requirement_set")
        if membership_version:
            assessment.used_fact_versions = _unique(assessment.used_fact_versions + [membership_version])
        unknown_criteria = any(criterion.status == "unknown" and criterion.name not in CALL_FIELDS for criterion in assessment.criteria)
        missing_deadline = deadlines[target_id] is None
        invalid_required = any(task_id in invalid for task_id in required)
        waiting = [result for result in target_results if result.status == "waiting"]
        excluded = modes[target_id] == "excluded"
        if excluded:
            assessment.readiness, assessment.schedule_status = "excluded", "excluded"
        elif invalid_required or invalid_exam:
            assessment.readiness, assessment.schedule_status = "blocked", "cannot_certify"
            assessment.reasons.append("Invalid prerequisite or calendar data prevents certification.")
        elif any(task_id in proof_tasks for task_id in required):
            assessment.readiness, assessment.schedule_status = "capacity_shortfall", "infeasible"
            assessment.reasons.append("This target participates in a combined workload whose lower bound exceeds attainable shared capacity; the chosen target combination is infeasible.")
        elif waiting:
            assessment.readiness, assessment.schedule_status = "waiting_external", "cannot_certify"
            assessment.reasons.append("External receipt is unobserved; elapsed planning time cannot satisfy it.")
        elif modes[target_id] != "current":
            assessment.readiness = "preparation_only" if modes[target_id] == "preparation" else "needs_review"
            assessment.schedule_status = "cannot_certify"
        elif missing_deadline or unknown_criteria or assessment.eligibility == "needs_review" or opportunities[target_id].verification == "uncertain" or not required:
            assessment.readiness, assessment.schedule_status = "needs_review", "cannot_certify"
        elif any(result.status in {"blocked", "unscheduled"} for result in target_results):
            assessment.readiness, assessment.schedule_status = "incomplete", "at_risk"
            assessment.reasons.append("The allocation heuristic did not fit every task; no mathematical impossibility claim is made.")
        else:
            assessment.schedule_status = "feasible"
            assessment.readiness = "ready" if all(result.status == "completed" for result in target_results) else "preparing"
            assessment.reasons.append("All graph-required work fits conservative estimates under the stated availability assumption.")
        if missing_deadline and not excluded:
            assessment.reasons.append("A supported timezone-aware deadline is missing; preparation dates do not certify timely submission.")
        assessment.reasons = _unique(assessment.reasons)

    used_versions = {version for assessment in assessments.values() for version in assessment.used_fact_versions}
    used_versions.update(version for result in plan_tasks.values() for version in result.fact_version_ids)
    fact_versions = {key: version for key, version in context.fact_versions.items() if version in used_versions}
    for target_id, opportunity in opportunities.items():
        for fact in opportunity.facts:
            version = _version(context, target_id, fact)
            if version in used_versions:
                fact_versions[f"{target_id}/{fact.name}"] = version

    if previous:
        for task_id, result in plan_tasks.items():
            old = old_tasks.get(task_id)
            if old and result.week_allocations != old.week_allocations and task_id not in set(impact.affected_task_ids if impact else []) and old.status != "completed":
                warnings.append(f"{result.title}: dates moved because the combined capacity or prerequisite calendar changed; its recipe and compatible completion were preserved.")
        if retained:
            warnings.append("Retained compatible completed work: " + ", ".join(sorted(retained)) + ".")
    scheduled_now = [
        result for task_id, result in plan_tasks.items()
        if result.status == "scheduled" and all(
            plan_tasks[dependency].status == "completed" and finished.get(dependency, end) <= start
            for dependency in result.dependencies
        )
    ]
    scheduled_now.sort(key=lambda result: (min(result.week_allocations, default=end.date().isoformat()), task_deadlines[result.task_id] or end, result.task_id))
    if scheduled_now:
        next_action = scheduled_now[0].title
    else:
        waiting_now = [result for result in plan_tasks.values() if result.status == "waiting" and all(
            plan_tasks[dependency].status == "completed" and finished.get(dependency, end) <= start
            for dependency in result.dependencies
        )]
        if waiting_now:
            next_action = waiting_now[0].title + "; record receipt only after it is observed."
        elif any(assessment.readiness == "ready" for assessment in assessments.values()):
            next_action = "Review the sourced requirements and current portal before any manual application submission."
        elif any(assessment.schedule_status == "infeasible" for assessment in assessments.values()):
            next_action = "Reduce the selected workload or revise availability; the combined lower-bound workload exceeds capacity."
        elif any(assessment.schedule_status == "at_risk" for assessment in assessments.values()):
            next_action = "Revise the selected workload or availability; the current allocation did not fit every task before its cutoff."
        elif assessments:
            next_action = "Review the unresolved source, profile, or portal conditions shown for the selected targets."
        else:
            next_action = "Select a sourced internship target to build a preparation plan."
    remaining = [tasks[task_id] for task_id in active_task_ids]
    weekly_used = {key: 0.0 for key in weekly_capacity}
    for result in plan_tasks.values():
        for key, value in result.week_allocations.items():
            weekly_used[key] += value
    normalized_profile = profile.model_copy(deep=True)
    normalized_profile.completed_task_ids = _unique(
        task_id for task_id in completion_claims
        if task_id in plan_tasks and plan_tasks[task_id].status == "completed"
        and not plan_tasks[task_id].waiting_for
    )
    revoked_claims = explicitly_completed - set(normalized_profile.completed_task_ids)
    if revoked_claims:
        warnings.append(
            "Removed completion claims that are outside or incompatible with the current recipe, "
            "unverified, or require an observed external event: " + ", ".join(sorted(revoked_claims)) + "."
        )
    plan = Plan(
        id=f"plan-{uuid4().hex}", selected_ids=selected_ids, profile=normalized_profile,
        targets=[assessments[key] for key in selected_ids], tasks=[plan_tasks[task_id] for task_id in order],
        evidence=[item.model_copy(deep=True) for item in context.evidence], fact_versions=fact_versions,
        total_hours_low=sum(task.hours_low for task in remaining), total_hours_high=sum(task.hours_high for task in remaining),
        available_hours=round(available_hours, 9), weekly_used={key: round(value, 9) for key, value in weekly_used.items()},
        roadmap=_roadmap(context, profile, plan_tasks, tasks),
        next_action=next_action, warnings=_unique(warnings),
        affected_target_ids=_unique(impact.affected_target_ids) if impact else [],
        affected_task_ids=_unique(impact.affected_task_ids) if impact else [],
    )
    from app.study import add_study_guidance
    return add_study_guidance(plan, context, profile, slots, finished, previous)
