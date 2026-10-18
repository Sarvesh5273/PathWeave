"""Explicit preparation estimates; these are authored recipes, never source rules."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime

from app.models import Opportunity, PreparationTask
from app.topics import SKILL_ALIASES, SKILL_FIELDS, SKILL_FOUNDATIONS, catalog_key


RECIPE_VERSION = "v1"
SHARED_CV = "shared/cv-base/v1"
SHARED_TRANSCRIPT = "shared/transcript-base/v1"


def _skill_key(value: str) -> str | None:
    return catalog_key(value)


@dataclass(frozen=True)
class DeliverableRecipe:
    id: str
    name: str
    task_id: str
    fact_names: tuple[str, ...]
    provenance: str = "source_requirement"


@dataclass(frozen=True)
class RecipeBundle:
    tasks: tuple[PreparationTask, ...]
    deliverables: tuple[DeliverableRecipe, ...]


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "_", value.lower()).strip("_")
    return slug[:60] or hashlib.sha256(value.encode()).hexdigest()[:12]


def _deadline(opportunity: Opportunity) -> str | None:
    fact = next((f for f in opportunity.facts if f.name == "application_deadline"), None)
    if fact is None or fact.status != "known" or not isinstance(fact.value, str):
        return None
    try:
        parsed = datetime.fromisoformat(fact.value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.isoformat() if parsed.tzinfo is not None else None


def recipes_for(opportunity: Opportunity) -> RecipeBundle:
    """Choose work from typed facts; ID prefixes are irrelevant to program behavior.

    Only explicitly reviewed base artifacts/exercises share work. Final documents
    and source-evidence reviews remain scoped. Completion means preparation work
    done, not assessed competence. Hours do not claim official required effort.
    """
    facts = {fact.name: fact for fact in opportunity.facts}
    due_at = _deadline(opportunity)
    tasks: dict[str, PreparationTask] = {}
    deliverables: list[DeliverableRecipe] = []
    final_tasks: list[str] = []

    def known(name: str, default=None):
        fact = facts.get(name)
        return fact.value if fact is not None and fact.status == "known" else default

    def add(
        suffix: str,
        title: str,
        low: float,
        high: float,
        names: list[str],
        *,
        dependencies: list[str] | None = None,
        waiting_for: str | None = None,
        artifact_type: str = "",
        shared_id: str | None = None,
    ) -> str:
        task_id = shared_id or f"{opportunity.id}/{suffix}/{RECIPE_VERSION}"
        tasks[task_id] = PreparationTask(
            id=task_id,
            title=title,
            category="Shared" if shared_id else opportunity.category,
            hours_low=low,
            hours_high=high,
            dependencies=dependencies or [],
            target_ids=[] if shared_id else [opportunity.id],
            fact_names=[] if shared_id else sorted(set(names)),
            waiting_for=waiting_for,
            artifact_type=artifact_type,
            provenance="planner_estimate:explicit_recipe_v1",
            due_at=None if shared_id else due_at,
        )
        return task_id

    def deliver(name: str, task_id: str, names: list[str], origin="source_requirement"):
        final_tasks.append(task_id)
        deliverables.append(DeliverableRecipe(
            id=f"{opportunity.id}/deliverable/{_slug(name)}",
            name=name,
            task_id=task_id,
            fact_names=tuple(sorted(set(names))),
            provenance=origin,
        ))

    document_fact = facts.get("documents")
    documents = document_fact.value if document_fact is not None else None
    supported_list = isinstance(documents, list) and all(isinstance(d, str) for d in documents)
    documents_known = bool(document_fact and document_fact.status == "known" and supported_list)
    # Retained historical requirements keep compatible preparation visible after
    # extraction failure. The verification task and unknown fact still block
    # certification; these documents are provisional until the source is repaired.
    historical_list = bool(document_fact and document_fact.excerpt and supported_list)
    documents = list(dict.fromkeys(documents)) if documents_known or historical_list else []
    common_names = ["documents", "application_deadline", "document_format"]

    if not documents_known:
        task = add("requirements-check", f"Verify {opportunity.program} document and portal requirements",
                   0.25, 0.5, ["documents", "portal_status", "application_deadline"],
                   artifact_type="requirements_verification")
        deliver("requirements_verification", task, ["documents"], "planner_estimate")

    if "cv" in documents:
        base = add("cv-base", "Prepare a reusable CV base", 1.0, 2.0, [],
                   shared_id=SHARED_CV, artifact_type="cv_base")
        task = add("cv-final", f"Tailor and check the CV for {opportunity.program}", 0.5, 1.0,
                   common_names, dependencies=[base], artifact_type="cv_final")
        deliver("cv", task, ["documents"])

    if "transcript" in documents:
        base = add("transcript-base", "Prepare the transcript source and course information", 0.5, 1.0,
                   [], shared_id=SHARED_TRANSCRIPT, artifact_type="transcript_base")
        translation = known("transcript_translation", "unknown")
        note = {
            "self": "Prepare the target's permitted self-translated transcript",
            "english_explanation": "Prepare the transcript with its required English explanation",
            "notarized": "Arrange the required notarized transcript translation",
        }.get(translation, "Check the target's transcript language and document format")
        task = add("transcript-final", f"{note} for {opportunity.program}", 0.5, 1.5,
                   common_names + ["transcript_translation"], dependencies=[base],
                   artifact_type="transcript_final")
        deliver("transcript", task, ["documents", "transcript_translation"])

    if "statement" in documents:
        limits = []
        for name, label in (("statement_max_words", "words"), ("statement_max_chars", "characters"),
                            ("statement_max_pages", "pages")):
            value = known(name)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
                limits.append(f"{value:g} {label}")
        title = f"Write a program-specific statement for {opportunity.program}"
        if limits:
            title += f" (limit: {', '.join(limits)})"
        names = common_names + ["statement_max_words", "statement_max_chars", "statement_max_pages"]
        task = add("statement-final", title, 2.0, 4.0, names, artifact_type="statement_final")
        deliver("statement", task, names)

    reference_count = known("reference_min")
    count_supported = (
        isinstance(reference_count, int) and not isinstance(reference_count, bool)
        and reference_count > 0
    )
    forbidden = known("reference_forbidden", False) is True
    if "reference" in documents and not forbidden:
        names = common_names + ["reference_min", "reference_max", "reference_submitter",
                               "reference_received_before_submit", "reference_forbidden",
                               "applicant_reference_upload_allowed"]
        count = str(reference_count) if count_supported else "unknown"
        submitter = known("reference_submitter", "unknown")
        submitter = str(submitter) if isinstance(submitter, str) else "unknown"
        receipt_required = known("reference_received_before_submit")
        receipt_value = "true" if receipt_required is True else "false" if receipt_required is False else "unknown"
        request = add("reference-request", f"Request {count} recommendation(s) for {opportunity.program}",
                      0.5, 1.0, names, artifact_type="reference_request")
        if receipt_required is True or receipt_required is None:
            event = (f"{opportunity.id}/references_received/min={count}"
                     f"/by={_slug(submitter)}/before_submit={receipt_value}")
            receipt = add("reference-receipt",
                          f"Confirm {count} recommendation(s) received by {opportunity.program}",
                          0, 0, names, dependencies=[request], waiting_for=event,
                          artifact_type="reference_receipt")
            deliver("reference", receipt, names)
        else:
            deliver("reference", request, names)

    conventional_documents = {
        "diploma_or_enrollment": ("Prepare the diploma or enrollment certificate", 0.25, 0.75),
        "identity_document": ("Check the required identity document", 0.25, 0.5),
        "id_photo": ("Prepare the required identification photo", 0.25, 0.5),
        "portfolio": ("Select and review a target-specific portfolio", 1.0, 2.0),
        "cover_letter": ("Write a target-specific cover letter", 1.0, 2.0),
    }
    for document in documents:
        if document in {"cv", "transcript", "statement", "reference"}:
            continue
        if document in conventional_documents:
            title, low, high = conventional_documents[document]
            task = add(f"{_slug(document)}-final", f"{title} for {opportunity.program}", low, high,
                       common_names, artifact_type=f"{_slug(document)}_final")
        else:
            task = add(f"verify-{_slug(document)}", f"Verify and prepare required document: {document}",
                       0.25, 0.5, common_names,
                       waiting_for=f"{opportunity.id}/manual_requirement_verified/{_slug(document)}",
                       artifact_type="unsupported_requirement")
        deliver(document, task, ["documents"])

    if known("institution_approval") is True:
        names = ["institution_approval", "application_deadline"]
        task = add("institution-approval", f"Confirm institution approval for {opportunity.program}",
                   0.5, 1.0, names,
                   waiting_for=f"{opportunity.id}/institution_approval_confirmed",
                   artifact_type="institution_approval")
        deliver("institution_approval", task, names)

    for name in sorted(SKILL_FIELDS & facts.keys()):
        fact = facts[name]
        names = [name]
        supported = (isinstance(fact.value, list) and bool(fact.value)
                     and all(isinstance(item, str) and item.strip() for item in fact.value))
        usable = supported and bool(fact.excerpt.strip()) and fact.status != "conflicting"
        if fact.status != "known" or not usable:
            task = add(f"verify-{name}", f"Verify {name.replace('_', ' ')} and preparation scope for {opportunity.program}",
                       0.25, 0.5, names, artifact_type="requirements_verification")
            deliver(f"verify_{name}", task, names, "planner_estimate")
        if not usable:
            continue
        items = list(dict.fromkeys(fact.value))
        # Language examples/alternatives do not make every language mandatory.
        # One identical language-neutral exercise is safe to share; the target's
        # review explicitly retains the source's options and quantifier uncertainty.
        alternatives = ("programming_languages" in name and
                        bool(re.search(r"\b(?:one of|at least one|such as|e\.g|or)\b", fact.excerpt, re.I)))
        if alternatives and any(_skill_key(item) is not None for item in items):
            # Unsupported options still need verification. If no option has a
            # reviewed recipe, do not manufacture a generic substitute syllabus.
            items = ["general purpose programming"] + [item for item in items if _skill_key(item) is None]
        reviewed: dict[str, list[str]] = {}
        for item in items:
            key = _skill_key(item)
            if key is None:
                digest = hashlib.sha256(item.encode()).hexdigest()[:10]
                task = add(f"verify-{name}-{digest}",
                           f"Verify preparation options for {item} for {opportunity.program} (no reviewed syllabus)",
                           0.25, 0.5, names, artifact_type="unsupported_requirement")
                deliver(f"{name}_{digest}", task, names, "planner_estimate")
            else:
                reviewed.setdefault(key, []).append(item)
        for key, labels in reviewed.items():
            title, low, high = SKILL_FOUNDATIONS[key]
            base = add(f"skill-{key}-base", title + " (preparation, not competence assessment)",
                       low, high, [], shared_id=f"shared/skill-{key}-foundation/v1",
                       artifact_type="skill_practice")
            qualifier = "; confirm the listed language options" if alternatives else ""
            task = add(f"{name}-{key}-review",
                       f"Review {', '.join(labels)} practice and existing evidence for {opportunity.program}{qualifier} (not assessed competence)",
                       0.5, 1.0, names, dependencies=[base], artifact_type="skill_evidence_review")
            deliver(f"{name}_{key}_preparation", task, names, "planner_estimate")

    # These are evidence-inventory exercises, not invented application documents
    # or hiring stages. No exercise manufactures professional/research experience.
    evidence_fields = {
        "portfolio": "Review existing portfolio evidence and source expectations",
        "software_development_experience": "Map existing software-development evidence and identify gaps",
        "data_cloud_ai_experience": "Map existing data/cloud/AI evidence and identify gaps",
        "host_unit_background": "Review the selected host unit's background expectations and existing evidence",
        "research_areas": "Map existing work to the source's research areas and record gaps",
        "research_interests": "Review source research interests against existing coursework and projects",
    }
    for name, title in evidence_fields.items():
        fact = facts.get(name)
        if fact is None or (fact.status == "known" and fact.value is False):
            continue
        if fact.status != "known" or not fact.excerpt.strip() or fact.value is None:
            title = f"Verify {name.replace('_', ' ')} expectations with the source"
            low, high, artifact = 0.25, 0.5, "requirements_verification"
        else:
            low, high, artifact = 1.0, 2.0, "experience_evidence_review"
        task = add(f"{name}-evidence-review", f"{title} for {opportunity.program} (not competence certification)",
                   low, high, [name], artifact_type=artifact)
        deliver(f"{name}_preparation", task, [name], "planner_estimate")

    source_conditions = [name for name,fact in facts.items() if
        (name.startswith('source_requirement_') or name.startswith('source_preference_') or
         name in {'application_process','interview_stages','coding_challenge','pathway_requirements'})
        and fact.status=='known' and fact.excerpt]
    if source_conditions:
        task = add('source-condition-review',
            f"Review the listed qualifications and selection process for {opportunity.program}",
            0.5,1.0,source_conditions,artifact_type='requirements_verification')
        deliver('source_condition_review',task,source_conditions,'planner_estimate')

    review_names = set(common_names + ["portal_status"])
    for task_id in final_tasks:
        review_names.update(tasks[task_id].fact_names)
    submission = add("application-review", f"Review readiness before submitting to {opportunity.program}",
                     0.5, 1.0, sorted(review_names), dependencies=sorted(set(final_tasks)),
                     artifact_type="submission")
    deliver("submission_readiness", submission, sorted(review_names), "planner_estimate")
    return RecipeBundle(tuple(tasks.values()), tuple(deliverables))
