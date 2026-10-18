"""Authored study guidance, separate from evidence-backed application assessment.

The existing planner allocates source-required work first. Recommended practice
uses only its remaining daily capacity and cannot create facts, evidence edges,
eligibility claims or application readiness. No network or graph writes occur.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from app.models import GraphContext, Plan, PlanTask, ProfileState, RoadmapTopic
from app.topics import TOPIC_CATALOG

EXTRA_TOPICS = {
    "project_story": {
        "title": "Explain your projects", "family": "Interview practice", "prerequisites": [],
        "practice": ("Rehearse a five-minute walkthrough of one real project", 1.0, 2.0),
        "resources": [{"title": "MIT CAPD: Interview preparation", "url": "https://capd.mit.edu/channels/interview/"}],
    },
    "behavioral": {
        "title": "Behavioral questions & clear answers", "family": "Interview practice", "prerequisites": [],
        "practice": ("Write and rehearse three examples from your own experience", 1.0, 2.0),
        "resources": [{"title": "MIT CAPD: Interview preparation", "url": "https://capd.mit.edu/channels/interview/"}],
    },
    "mock_interview": {
        "title": "Mock interview & revision", "family": "Interview practice",
        "prerequisites": ["project_story", "behavioral"],
        "practice": ("Run a 30-minute mock interview and revise your weakest answers", 1.0, 2.0),
        "resources": [{"title": "MIT CAPD: Interview preparation", "url": "https://capd.mit.edu/channels/interview/"}],
    },
    "research_reading": {
        "title": "Read and discuss a research paper", "family": "Research", "prerequisites": [],
        "practice": ("Read one paper relevant to your chosen lab and write a one-page critique", 2.0, 4.0),
        "resources": [{"title": "MIT Communication Lab: research communication guides", "url": "https://mitcommlab.mit.edu/"}],
    },
    "research_methods": {
        "title": "Research methods & experiment reasoning", "family": "Research",
        "prerequisites": ["research_reading"],
        "practice": ("Explain a paper's method and design one follow-up experiment", 2.0, 3.0),
        "resources": [{"title": "MIT Communication Lab: research communication guides", "url": "https://mitcommlab.mit.edu/"}],
    },
}

DETAILS = {
    "programming": (["Variables, types and control flow", "Functions and decomposition", "Collections, edge cases and debugging"],
                    "Write a small program without copying a solution; test normal and edge cases."),
    "data_structures": (["Arrays and strings", "Hash maps and sets", "Stacks, queues and linked lists", "Trees and graphs"],
                        "Solve one array problem, one hash-map problem and one tree traversal; explain your choices."),
    "algorithms": (["Sorting and binary search", "Two pointers and sliding windows", "Recursion and traversal", "When to use each pattern"],
                   "Solve three small problems using different patterns, then explain and test each solution."),
    "complexity": (["Big-O time and space", "Nested loops and recursion", "Comparing brute-force and improved solutions"],
                   "Give time and space costs for your solutions and explain one useful optimization."),
    "object_oriented_programming": (["Classes, objects and interfaces", "Encapsulation and composition", "Inheritance trade-offs"],
                                   "Model a small real-world problem; explain why you chose composition or inheritance."),
    "object_oriented_design": (["Responsibilities and interfaces", "Coupling and cohesion", "Trade-offs in a small design"],
                              "Sketch a small design, test its behavior and explain two trade-offs."),
    "sql": (["SELECT, filtering and aggregation", "JOINs and relationships", "NULLs and duplicate rows"],
            "Write a join and a grouped query against a small dataset; check the returned rows."),
    "statistics": (["Distributions, mean and variance", "Sampling and uncertainty", "Correlation versus causation"],
                   "Summarize a dataset and explain one limitation of the conclusions."),
    "data_analysis": (["Loading and cleaning data", "Missing values and grouping", "Explaining a useful finding"],
                      "Analyze a small dataset, record cleaning decisions and communicate one finding."),
    "machine_learning": (["Train/validation/test splits", "Baselines, overfitting and leakage", "Choosing an evaluation metric"],
                         "Compare a simple model with a baseline and explain evaluation limitations."),
    "deep_learning": (["Neural network building blocks", "Loss and optimization", "Overfitting and evaluation"],
                      "Walk through a small neural network example and explain its limitations."),
    "git": (["Commits and branches", "Reading diffs", "Resolving a small merge conflict"],
            "Make a change on a branch, review the diff and merge it safely."),
    "software_testing": (["Unit and integration tests", "Boundary cases", "Interpreting failures"],
                         "Write tests for a small function, including a boundary case and a failure."),
    "linux": (["Files and permissions", "Pipes and text tools", "Processes and logs"],
              "Use shell commands to inspect a small project and diagnose one simple issue."),
    "docker": (["Images and containers", "Ports and volumes", "Reproducible local runs"],
               "Run a small application in a container and explain how its ports and storage work."),
    "cloud_computing": (["Compute, storage and networking", "Access control", "Cost and reliability trade-offs"],
                        "Explain a small deployment design and how you would limit cost and access."),
    "web_development": (["HTML structure and accessibility", "CSS layout and responsive behavior", "JavaScript events and HTTP"],
                        "Build a small responsive page and explain how its data and interactions work."),
    "project_story": (["Problem and intended user", "Your actual contribution", "Technical decisions and trade-offs", "Results, limitations and next steps"],
                      "Explain one real project in five minutes and answer two follow-up questions without inventing experience."),
    "behavioral": (["Situation, task, action and result", "Teamwork and disagreement", "A setback and what you changed"],
                   "Rehearse three truthful examples with a clear personal contribution and outcome."),
    "mock_interview": (["Explain your reasoning aloud", "Ask clarifying questions", "Review mistakes and gaps"],
                       "Finish a mock session, record three specific gaps and practise the weakest one again."),
    "research_reading": (["Research question and motivation", "Method, evidence and results", "Assumptions and limitations"],
                        "Summarize one relevant paper and prepare two thoughtful questions about it."),
    "research_methods": (["Hypotheses and controls", "Measures and reproducibility", "Alternative explanations"],
                         "Propose an experiment with a measurable outcome and identify two limitations."),
}
TRACKS = {
    "software": ["programming", "data_structures", "algorithms", "complexity", "object_oriented_programming",
                 "sql", "software_testing", "project_story", "behavioral", "mock_interview"],
    "data": ["python", "statistics", "sql", "data_analysis", "machine_learning",
             "project_story", "behavioral", "mock_interview"],
    "research": ["research_reading", "research_methods", "project_story", "behavioral", "mock_interview"],
    "general": ["project_story", "behavioral", "mock_interview"],
}


def choose_track(context: GraphContext, requested: str) -> tuple[str, str]:
    if requested != "auto":
        return requested, "You chose this preparation track. Recommendations are not confirmed employer requirements."
    keys = {topic.key for topic in context.topics}
    text = " ".join(op.program + " " + op.summary for op in context.opportunities).casefold()
    if keys & {"machine_learning", "deep_learning", "statistics", "data_analysis"} or re.search(
            r"\b(data scien\w*|data analyst|machine learning)\b", text):
        return "data", "Suggested from the selected topics or role description. Change the track if this is not your goal."
    if keys & {"programming", "data_structures", "algorithms", "web_development"} or re.search(
            r"\b(software|frontend|front-end|backend|back-end|full-stack|developer)\b", text):
        return "software", "Suggested from the selected topics or role description. Change the track if this is not your goal."
    if re.search(r"\b(research|laboratory|phd)\b", text):
        return "research", "Research preparation suggested from the selected description; the exact interview format is unconfirmed."
    return "general", (
        "The selected sources do not establish a technical interview syllabus. "
        "Start with general interview practice, or choose Software, Data & ML, or Research to get a specific topic plan."
    )


def _ordered(keys: list[str], catalog: dict) -> list[str]:
    ordered, visiting = [], set()

    def visit(key):
        if key in ordered or key in visiting or key not in catalog:
            return
        visiting.add(key)
        for prerequisite in catalog[key].get("prerequisites", []):
            visit(prerequisite)
        visiting.remove(key)
        ordered.append(key)

    for key in keys:
        visit(key)
    return ordered


def _allocate(hours: float, release: datetime, slots: list[dict]) -> tuple[dict[str, float], datetime | None]:
    """Use only residual daily capacity left by application/source tasks."""
    remaining, allocations = hours, {}
    for slot in slots:
        left = max(slot["start"], slot["cursor"], release)
        if slot["hours"] <= 1e-8 or left >= slot["end"]:
            continue
        capacity = min(slot["hours"] - slot["used"],
                       slot["hours"] * (slot["end"] - left).total_seconds() / 86400)
        if capacity <= 1e-8:
            continue
        assigned = min(remaining, capacity)
        finish = left + timedelta(seconds=assigned / slot["hours"] * 86400)
        slot["used"] += assigned
        slot["cursor"] = finish
        allocations[slot["week"]] = allocations.get(slot["week"], 0) + assigned
        remaining -= assigned
        if remaining <= 1e-8:
            return allocations, finish
    return allocations, None


def add_study_guidance(plan: Plan, context: GraphContext, profile: ProfileState,
                       slots: list[dict], source_finished: dict[str, datetime],
                       previous: Plan | None) -> Plan:
    """Enrich this new proposal only. Never modify saved plans or source facts."""
    track, reason = choose_track(context, profile.study_track)
    plan.study_track, plan.study_track_reason = track, reason
    catalog = {**TOPIC_CATALOG, **EXTRA_TOPICS}
    source = {entry.key: entry for entry in plan.roadmap}
    roots = list(source)
    if track in TRACKS and plan.selected_ids:
        roots += TRACKS[track]
    keys = _ordered(roots, catalog)
    # Retain any graph topic not represented in the authored starter catalog.
    keys += [key for key in source if key not in keys]
    if track == "source_only":
        keys = list(source)
    existing = {task.task_id: task for task in plan.tasks}
    task_for_key = {}
    for key in keys:
        linked = next((task_id for task_id in source.get(key, RoadmapTopic(key=key, title="")).task_ids
                       if task_id in existing), None)
        if linked:
            task_for_key[key] = linked
        elif track in TRACKS and key in catalog:
            task_for_key[key] = f"study/{key}/v1"
    claims = profile.completed_task_ids
    if "completed_task_ids" not in profile.model_fields_set and previous and previous.profile.id == profile.id:
        claims = previous.profile.completed_task_ids
    completed = set(claims)
    finished = dict(source_finished)
    begin = slots[0]["start"] if slots else None
    entries = []
    for index, key in enumerate(keys):
        spec = catalog.get(key, {})
        entry = source[key].model_copy(deep=True) if key in source else RoadmapTopic(
            key=key, title=spec["title"], family=spec["family"], basis="recommended",
            prerequisites=list(spec.get("prerequisites", [])), resources=list(spec.get("resources", [])),
        )
        entry.order, entry.start_here = index + 1, False
        entry.rating = profile.skill_ratings.get(key, "")
        if not entry.resources:
            entry.resources = list(spec.get("resources", []))
        language = key in {"python", "java", "cpp", "c", "javascript", "typescript"}
        details = DETAILS.get(key, (
            ["Syntax and control flow", "Functions and collections", "Error handling, debugging and tests"] if language
            else [f"Core concepts in {entry.title}", "A worked example", "Common mistakes and limitations"],
            "Complete a small tested exercise and explain the result and edge cases." if language
            else "Explain the main concepts and work through an example using the linked resources.",
        ))
        entry.learn = list(details[0])
        entry.done_when = details[1]
        practice, low, high = spec.get("practice", ("Review this topic using its linked resources", 0, 0))
        entry.practice = practice
        task_id = task_for_key.get(key)
        task = existing.get(task_id)
        if task_id and task is None and begin is not None:
            if entry.rating == "comfortable":
                low, high = min(low, 0.5), min(high, 1.0)
            dependencies = [task_for_key[value] for value in entry.prerequisites if value in task_for_key]
            task = PlanTask(task_id=task_id, title=practice, category="Study",
                            hours_low=low, hours_high=high, dependencies=dependencies)
            if task_id in completed:
                task.status, task.reason = "completed", "Study practice marked complete by you; not an independent skill assessment."
                finished[task_id] = begin
                plan.profile.completed_task_ids.append(task_id)
            elif any(value not in finished for value in dependencies):
                task.status, task.reason = "blocked", "Finish or make time for the earlier study topic first."
            else:
                release = max([begin] + [finished[value] for value in dependencies])
                task.week_allocations, finish = _allocate(high, release, slots)
                if finish is not None:
                    task.status, task.reason = "scheduled", "Recommended practice fits the remaining shared budget."
                    finished[task_id] = finish
                else:
                    task.reason = "Not fully scheduled. Increase available time, extend the horizon, or focus on earlier topics."
            plan.tasks.append(task)
            existing[task_id] = task
            if task.status != "completed":
                plan.total_hours_low += low
                plan.total_hours_high += high
            # Provenance is already carried by basis and explained once in the
            # UI. Do not repeat the same legal caveat on every topic.
            entry.note = "You marked this comfortable; a shorter review is suggested." if entry.rating == "comfortable" else ""
        if task:
            entry.task_ids = [task.task_id]
            entry.task_status = task.status
            entry.scheduled = task.status in {"scheduled", "completed"}
            entry.hours_low, entry.hours_high = task.hours_low, task.hours_high
            entry.week_allocations = dict(task.week_allocations)
            if task.category == "Study" and task.status != "completed":
                for week, hours in task.week_allocations.items():
                    plan.weekly_used[week] = round(plan.weekly_used.get(week, 0) + hours, 9)
        entries.append(entry)
    plan.roadmap = entries
    learning_ids = {task_id for entry in entries for task_id in entry.task_ids}
    remaining = [existing[value] for value in learning_ids if existing[value].status != "completed"]
    plan.study_hours_low = sum(task.hours_low for task in remaining)
    plan.study_hours_high = sum(task.hours_high for task in remaining)
    plan.application_hours_low = max(0, plan.total_hours_low - plan.study_hours_low)
    plan.application_hours_high = max(0, plan.total_hours_high - plan.study_hours_high)
    candidates = [entry for entry in entries if entry.task_status != "completed" and entry.task_ids
                  and entry.task_status != "blocked" and (entry.scheduled or entry.week_allocations)
                  and all(existing[dependency].status == "completed"
                          for task_id in entry.task_ids for dependency in existing[task_id].dependencies)]
    next_topic = next((entry for entry in candidates if entry.rating != "comfortable"), candidates[0] if candidates else None)
    if next_topic:
        next_topic.start_here = True
        plan.next_action = "Study next: " + next_topic.title
    elif entries and all(entry.task_status == "completed" for entry in entries):
        plan.next_action = "Your planned study practice is marked complete. Revisit weak topics or run another mock interview."
    elif entries and track != "source_only":
        plan.next_action = "Make time for your first study topic: increase availability or extend the planning horizon."
    return plan
