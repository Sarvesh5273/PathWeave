"""Behavior tests execute Cypher on a unique disposable real FalkorDB graph.

Unavailable DB tests skip explicitly; they never replace graph queries with fixtures.
Set REQUIRE_FALKORDB=1 in the proof command so unavailable storage fails the gate.
"""

from __future__ import annotations

import os
from dataclasses import replace
from uuid import uuid4

import pytest
from falkordb import FalkorDB
from redis.exceptions import RedisError

from app.config import settings
from app.graph import GraphIntegrityError, GraphStore, StalePlanError, fact_version_id, requirement_set
from app.models import Fact, Opportunity, Plan, PlanTask, ProfileState, SourceSnapshot, TargetAssessment
from app.recipes import SHARED_CV, SHARED_TRANSCRIPT


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


def opportunity(target="epfl-test-2027", *, references=0):
    is_oist = references > 0 or "oist" in target
    source_url = f"https://{'admissions.oist.jp' if is_oist else 'summer.epfl.ch'}/test-fixture"
    facts = [
        Fact(name="documents", value=["cv", "transcript", "statement"] + (["reference"] if references else []),
             status="known", kind="requirement", excerpt="Documents required: CV, transcript, statement.",
             source_url=source_url),
        Fact(name="portal_status", value="open", status="known", kind="information",
             excerpt="The application portal is open.", source_url=source_url),
        Fact(name="application_deadline", value="2026-12-15T23:59:00+09:00", status="known", kind="requirement",
             excerpt="Apply by 15 December 2026, 23:59 JST.", source_url=source_url),
        Fact(name="reference_min", value=references, status="known", kind="requirement",
             excerpt=f"{references} recommendation letters required.", source_url=source_url),
        Fact(name="reference_received_before_submit", value=bool(references), status="known", kind="requirement",
             excerpt="Recommendations must be received before submission." if references else "No references needed.",
             source_url=source_url),
        Fact(name="reference_submitter", value="faculty" if references else "none", status="known", kind="information",
             excerpt="Faculty submits the reference." if references else "No reference required.", source_url=source_url),
        Fact(name="statement_max_words", value=400, status="known", kind="requirement",
             excerpt="Your statement is limited to 400 words.", source_url=source_url),
        Fact(name="statement_max_chars", value=None, status="unknown", kind="information", source_url=source_url),
        Fact(name="transcript_translation", value="english_explanation", status="known", kind="requirement",
             excerpt="Include an English explanation for the transcript.", source_url=source_url),
    ]
    return Opportunity(id=target, program="OIST Research Internship" if is_oist else "Summer@EPFL",
                       cycle="2027 synthetic test fixture", source_url=source_url,
                       mode="synthetic", call_status="open", facts=facts)


def proposal(store, selected_ids, plan_id="proposal-one"):
    context = store.context(selected_ids)
    tasks = []
    for task in context.tasks:
        versions = sorted({context.fact_versions[f"{target}/{name}"]
                           for target in task.target_ids for name in task.fact_names
                           if f"{target}/{name}" in context.fact_versions})
        tasks.append(PlanTask(
            task_id=task.id, title=task.title, category=task.category,
            target_ids=task.target_ids, dependencies=task.dependencies,
            waiting_for=task.waiting_for,
            status="completed" if task.id == SHARED_CV else "waiting" if task.waiting_for else "scheduled",
            hours_low=task.hours_low, hours_high=task.hours_high, fact_version_ids=versions,
        ))
    return Plan(id=plan_id, selected_ids=selected_ids, profile=ProfileState(id="demo-student", completed_task_ids=[SHARED_CV]),
                targets=[TargetAssessment(target_id=target,
                           used_fact_versions=[v for key, v in context.fact_versions.items() if key.startswith(f"{target}/")])
                         for target in selected_ids],
                tasks=tasks, evidence=context.evidence, fact_versions=context.fact_versions)


def set_fact(opportunity, name, value):
    revised = opportunity.model_copy(deep=True)
    fact = next(f for f in revised.facts if f.name == name)
    fact.value = value
    fact.excerpt = f"Synthetic test mutation: {name} = {value}"
    return revised


def test_genuine_prerequisite_closure_and_compatible_base_work(store):
    epfl = opportunity()
    oist = opportunity("oist-test-2027", references=1)
    store.upsert_opportunity(epfl)
    store.upsert_opportunity(oist)
    context = store.context([epfl.id, oist.id])
    by_id = {task.id: task for task in context.tasks}
    assert sum(task.id == SHARED_CV for task in context.tasks) == 1
    assert sum(task.id == SHARED_TRANSCRIPT for task in context.tasks) == 1
    assert by_id[SHARED_CV].target_ids == sorted([epfl.id, oist.id])
    assert by_id[SHARED_CV].fact_names == []
    assert f"{epfl.id}/statement-final/v1" in by_id
    assert f"{oist.id}/statement-final/v1" in by_id
    assert not any(task.id.startswith(f"{epfl.id}/reference") for task in context.tasks)
    receipt = by_id[f"{oist.id}/reference-receipt/v1"]
    assert receipt.waiting_for == f"{oist.id}/references_received/min=1/by=faculty/before_submit=true"
    assert receipt.dependencies == [f"{oist.id}/reference-request/v1"]
    submission = by_id[f"{oist.id}/application-review/v1"]
    assert submission.artifact_type == "submission"
    assert receipt.id in submission.dependencies
    assert receipt.hours_high == 0
    cv_evidence = [path for path in context.evidence if path.target_id == epfl.id and path.task_id == SHARED_CV]
    assert any(len(path.nodes) >= 5 and path.nodes[-1] == SHARED_CV for path in cv_evidence)
    assert any(path.excerpt and "CURRENT" in path.relationship and path.source_url == oist.source_url
               for path in context.evidence)
    assert context.fact_versions[f"{epfl.id}/reference_min"] != context.fact_versions[f"{oist.id}/reference_min"]


def test_noop_refresh_metadata_and_document_reordering_do_not_stale_plan(store):
    target = opportunity()
    snapshot = SourceSnapshot(id="snapshot-one", url=target.source_url, text="old source body", mode="synthetic")
    store.upsert_opportunity(target, snapshot)
    plan = proposal(store, [target.id])
    store.save_plan(plan)
    before = store.get_opportunity(target.id)
    reordered = target.model_copy(deep=True)
    reordered.checked_at = "2026-10-17T00:00:00+05:30"
    next(f for f in reordered.facts if f.name == "documents").value.reverse()
    for fact in reordered.facts:
        fact.excerpt = fact.excerpt + " Nonsemantic source spacing changed."
    changed_snapshot = snapshot.model_copy(update={"id": "snapshot-two", "text": "New nav, same rules",
                                                     "checked_at": reordered.checked_at})
    impact = store.upsert_opportunity(reordered, changed_snapshot)
    assert impact.semantic_change is False
    assert impact.changes == [] and impact.affected_plan_ids == []
    assert store.get_plan(plan.id).status == "proposed"
    assert {f.name: f.version_id for f in store.get_opportunity(target.id).facts} == {
        f.name: f.version_id for f in before.facts}
    source_rows = store._graph.ro_query("MATCH (:FactVersion)-[:SUPPORTED_BY]->(s:Source) "
                                       "RETURN count(DISTINCT s)").result_set
    assert source_rows[0][0] == 2


def test_selective_reference_impact_preserves_epfl_and_completed_shared_work(store):
    epfl = opportunity()
    oist = opportunity("oist-test-2027", references=1)
    store.upsert_opportunity(epfl)
    store.upsert_opportunity(oist)
    plan = proposal(store, [epfl.id, oist.id])
    store.save_plan(plan)
    store.accept_plan(plan.id)
    impact = store.upsert_opportunity(set_fact(oist, "reference_min", 2))
    assert impact.semantic_change
    assert [(change.opportunity_id, change.fact_name) for change in impact.changes] == [(oist.id, "reference_min")]
    assert impact.affected_plan_ids == [plan.id]
    assert impact.affected_target_ids == [oist.id]
    assert impact.affected_task_ids == sorted([
        f"{oist.id}/reference-request/v1", f"{oist.id}/reference-receipt/v1", f"{oist.id}/application-review/v1",
    ])
    assert SHARED_CV in impact.preserved_task_ids
    assert SHARED_TRANSCRIPT in impact.preserved_task_ids
    assert f"{epfl.id}/statement-final/v1" in impact.preserved_task_ids
    assert all(not task.startswith(epfl.id) for task in impact.affected_task_ids)
    assert any("/reference_min@" in node for path in impact.paths for node in path.nodes)
    old = store.get_plan(plan.id)
    assert old.status == "accepted"
    assert old.affected_target_ids == [oist.id] and old.warnings
    assert next(t for t in old.tasks if t.task_id == SHARED_CV).status == "completed"
    with pytest.raises(StalePlanError):
        store.accept_plan(plan.id)
    current_context = store.context([epfl.id, oist.id])
    assert next(t for t in current_context.tasks if t.id == f"{oist.id}/reference-receipt/v1").waiting_for != (
        next(t for t in plan.tasks if t.task_id == f"{oist.id}/reference-receipt/v1").waiting_for)


def test_actual_dependency_edge_changes_context_and_reverse_impact(store):
    target = opportunity("oist-test-2027", references=1)
    store.upsert_opportunity(target)
    plan = proposal(store, [target.id])
    submission = next(t for t in plan.tasks if t.task_id.endswith("/application-review/v1"))
    submission.fact_version_ids = []
    store.save_plan(plan)
    impact = store.upsert_opportunity(set_fact(target, "reference_min", 2))
    assert submission.task_id in impact.affected_task_ids
    assert any("/reference-receipt/v1" in node for p in impact.paths if p.task_id == submission.task_id for node in p.nodes)
    base_before = store.context([target.id])
    cv_id = f"{target.id}/cv-final/v1"
    store._graph.query("MATCH (task:PrepTask {id:$task})-[edge:DEPENDS_ON]->(base:PrepTask {id:$base}) DELETE edge",
                       params={"task": cv_id, "base": SHARED_CV})
    context_after = store.context([target.id])
    assert any(t.id == SHARED_CV for t in base_before.tasks)
    assert not any(t.id == SHARED_CV for t in context_after.tasks)
    assert next(t for t in context_after.tasks if t.id == cv_id).dependencies == []


def test_repealed_receipt_condition_removes_old_support_edge(store):
    target = opportunity("oist-test-2027", references=1)
    store.upsert_opportunity(target)
    assert any(task.id.endswith("/reference-receipt/v1") for task in store.context([target.id]).tasks)
    changed = set_fact(target, "reference_received_before_submit", False)
    store.upsert_opportunity(changed)
    context = store.context([target.id])
    assert not any(task.id.endswith("/reference-receipt/v1") for task in context.tasks)
    submission = next(t for t in context.tasks if t.artifact_type == "submission")
    assert f"{target.id}/reference-request/v1" in submission.dependencies
    assert f"{target.id}/reference-receipt/v1" not in submission.dependencies


def test_source_uncertainty_retains_history_and_blocks_stale_acceptance(store):
    target = opportunity()
    store.upsert_opportunity(target)
    plan = proposal(store, [target.id])
    store.save_plan(plan)
    original = store.get_opportunity(target.id)
    original_versions = {fact.name: fact.version_id for fact in original.facts}
    impact = store.mark_source_uncertain(target.source_url)
    current = store.get_opportunity(target.id)
    assert impact.semantic_change
    assert current.verification == "uncertain" and current.call_status == "unknown"
    assert all(fact.status == "unknown" for fact in current.facts)
    current_context = store.context([target.id])
    assert any(task.id == SHARED_CV for task in current_context.tasks)
    assert any(task.artifact_type == "requirements_verification" for task in current_context.tasks)
    assert next(f.value for f in current.facts if f.name == "documents") == next(
        f.value for f in original.facts if f.name == "documents")
    retained = {row[0] for row in store._graph.ro_query("MATCH (v:FactVersion) RETURN v.id").result_set}
    assert set(original_versions.values()) <= retained
    assert store.get_plan(plan.id).status == "stale"
    with pytest.raises(StalePlanError):
        store.accept_plan(plan.id)
    again = store.mark_source_uncertain(target.source_url)
    assert not again.semantic_change


def test_partial_refresh_does_not_erase_omitted_rule(store):
    target = opportunity()
    store.upsert_opportunity(target)
    plan = proposal(store, [target.id])
    store.save_plan(plan)
    partial = target.model_copy(deep=True)
    partial.facts = [fact for fact in partial.facts if fact.name != "statement_max_words"]
    impact = store.upsert_opportunity(partial)
    fact = next(f for f in store.get_opportunity(target.id).facts if f.name == "statement_max_words")
    assert fact.status == "unknown" and fact.value == 400
    assert [change.fact_name for change in impact.changes] == ["statement_max_words"]
    assert f"{target.id}/statement-final/v1" in impact.affected_task_ids
    assert SHARED_CV in impact.preserved_task_ids


def test_unknown_placeholder_preserves_former_requirement_kind_and_value(store):
    target = opportunity()
    store.upsert_opportunity(target)
    placeholder = target.model_copy(deep=True)
    fact = next(f for f in placeholder.facts if f.name == "statement_max_words")
    fact.status = "unknown"
    fact.kind = "information"
    fact.value = None
    fact.excerpt = ""
    impact = store.upsert_opportunity(placeholder)
    current = next(f for f in store.get_opportunity(target.id).facts if f.name == "statement_max_words")
    assert current.status == "unknown" and current.kind == "requirement"
    assert current.value == 400 and current.excerpt == "Your statement is limited to 400 words."
    assert [c.fact_name for c in impact.changes] == ["statement_max_words"]


def test_unused_information_change_does_not_stale_decisions_or_acceptance(store):
    target = opportunity()
    target.facts.append(Fact(name="funding", value=["travel"], kind="information", status="known",
                             excerpt="Travel support is available.", source_url=target.source_url))
    store.upsert_opportunity(target)
    plan = proposal(store, [target.id])
    funding_version = plan.fact_versions[f"{target.id}/funding"]
    plan.targets[0].used_fact_versions.remove(funding_version)
    store.save_plan(plan)
    impact = store.upsert_opportunity(set_fact(target, "funding", ["travel", "accommodation"]))
    assert impact.semantic_change
    assert not impact.affected_plan_ids and not impact.affected_target_ids and not impact.affected_task_ids
    assert store.get_plan(plan.id).status == "proposed"
    assert store.accept_plan(plan.id).status == "accepted"


def test_document_format_changes_specific_final_work_not_shared_bases(store):
    target = opportunity()
    target.facts.append(Fact(name="document_format", value="pdf", status="known", kind="requirement",
                             excerpt="Documents must be submitted as PDF.", source_url=target.source_url))
    target.facts.append(Fact(name="statement_max_pages", value=2, status="known", kind="requirement",
                             excerpt="Statement must be at most two pages.", source_url=target.source_url))
    store.upsert_opportunity(target)
    plan = proposal(store, [target.id])
    store.save_plan(plan)
    format_impact = store.upsert_opportunity(set_fact(target, "document_format", "docx"))
    assert format_impact.affected_task_ids == sorted([
        f"{target.id}/application-review/v1", f"{target.id}/cv-final/v1",
        f"{target.id}/statement-final/v1", f"{target.id}/transcript-final/v1",
    ])
    assert SHARED_CV in format_impact.preserved_task_ids
    changed = store.get_opportunity(target.id)
    second = proposal(store, [target.id], "format-second")
    store.save_plan(second)
    pages_impact = store.upsert_opportunity(set_fact(changed, "statement_max_pages", 1))
    assert pages_impact.affected_task_ids == sorted([
        f"{target.id}/application-review/v1", f"{target.id}/statement-final/v1",
    ])


def test_expired_deadline_closes_call_without_inventing_portal_status(store):
    target = opportunity("oist-spring-expired", references=1)
    target = set_fact(target, "application_deadline", "2026-10-01T15:00:00+09:00")
    portal = next(f for f in target.facts if f.name == "portal_status")
    portal.status = "unknown"
    portal.value = None
    portal.excerpt = ""
    target.call_status = "closed"
    store.upsert_opportunity(target)
    current = store.get_opportunity(target.id)
    assert current.call_status == "closed"
    assert next(f for f in current.facts if f.name == "portal_status").status == "unknown"


def test_plan_immutable_acceptance_and_reconnect(store):
    target = opportunity()
    store.upsert_opportunity(target)
    plan = proposal(store, [target.id])
    assert store.save_plan(plan).status == "proposed"
    assert store.save_plan(plan).id == plan.id
    revised_body = plan.model_copy(deep=True)
    revised_body.next_action = "Different immutable plan body"
    with pytest.raises(ValueError, match="immutable"):
        store.save_plan(revised_body)
    assert store.accept_plan(plan.id).status == "accepted"
    assert store.accept_plan(plan.id).status == "accepted"
    reconnected = GraphStore(store.settings)
    recovered = reconnected.latest_plan()
    assert recovered.id == plan.id and recovered.status == "accepted"
    assert recovered.fact_versions == plan.fact_versions
    assert recovered.tasks == plan.tasks
    newer = proposal(store, [target.id], "proposal-two")
    store.save_plan(newer)
    assert store.latest_plan().id == newer.id
    assert store.get_plan(plan.id).status == "accepted"


def test_unsupported_documents_and_graph_view_are_explicit(store):
    target = opportunity("sim-oist-fixture", references=1)
    target = set_fact(target, "documents", ["cv", "transcript", "statement", "reference",
                                           "identity_document", "id_photo", "diploma_or_enrollment", "novel_attachment"])
    store.upsert_opportunity(target)
    context = store.context([target.id])
    unsupported = next(t for t in context.tasks if t.artifact_type == "unsupported_requirement")
    assert unsupported.waiting_for
    assert all(any(t.artifact_type == f"{name}_final" for t in context.tasks)
               for name in ["identity_document", "id_photo", "diploma_or_enrollment"])
    view = store.graph_view([target.id])
    assert len(view["nodes"]) <= 160 and len(view["edges"]) <= 240
    assert {edge["type"] for edge in view["edges"]} >= {"REQUIRES", "DEPENDS_ON", "CURRENT", "SUPPORTED_BY"}
    assert any(node["type"] == "Source" for node in view["nodes"])
    assert all(edge["source"] in {node["id"] for node in view["nodes"]}
               and edge["target"] in {node["id"] for node in view["nodes"]} for edge in view["edges"])


def test_unknown_unexcerpted_fact_cannot_be_certified(store):
    target = opportunity()
    next(f for f in target.facts if f.name == "application_deadline").excerpt = ""
    store.upsert_opportunity(target)
    fact = next(f for f in store.get_opportunity(target.id).facts if f.name == "application_deadline")
    assert fact.status == "unknown"
    assert all(task.due_at is None for task in store.context([target.id]).tasks)


def test_dependency_depth_guard_fails_explicitly(store):
    target = opportunity()
    store.upsert_opportunity(target)
    task_id = f"{target.id}/cv-final/v1"
    for index in range(9):
        next_id = f"test-depth-{index}"
        store._graph.query("MATCH (t:PrepTask {id:$task}) MERGE (p:PrepTask {id:$next}) "
                           "MERGE (t)-[:DEPENDS_ON]->(p)", params={"task": task_id, "next": next_id})
        task_id = next_id
    with pytest.raises(GraphIntegrityError, match="depth"):
        store.context([target.id])


def test_fact_version_excludes_metadata_and_includes_scope_kind_status():
    fact = Fact(name="reference_min", value=1, status="known", kind="requirement", excerpt="One letter", source_url="https://example.com")
    version = fact_version_id("oist-2027", fact)
    assert fact_version_id("oist-2027", fact.model_copy(update={"excerpt": "reformatted", "source_url": "https://example.org"})) == version
    assert fact_version_id("another-2027", fact) != version
    assert fact_version_id("oist-2027", fact.model_copy(update={"status": "unknown"})) != version
    assert fact_version_id("oist-2027", fact.model_copy(update={"kind": "preference"})) != version


def test_empty_graph_reads_are_read_only_and_selection_is_bounded(store):
    assert store.list_opportunities() == []
    assert store.get_opportunity("unknown") is None
    assert store.latest_plan() is None
    assert store.health()["initialized"] is False
    with pytest.raises(ValueError, match="three"):
        store.context(["one", "two", "three", "four"])
    with pytest.raises(ValueError):
        store.context(["one", "one"])


def test_recorded_source_graph_and_planner_integration(store):
    from app.planner import build_plan
    from app.sources import DiscoverService

    discovered = DiscoverService().load_examples()
    assert not discovered.errors
    snapshots = {snapshot.url: snapshot for snapshot in discovered.snapshots}
    for target in discovered.opportunities:
        store.upsert_opportunity(target, snapshots.get(target.source_url))
    selected = ["epfl-summer-2027", "oist-fall-2027"]
    context = store.context(selected)
    assert len(context.opportunities) == 2
    profile = ProfileState(completed_task_ids=[SHARED_CV])
    plan = build_plan(context, profile)
    saved = store.save_plan(plan)
    assert saved.id == plan.id and saved.status == "proposed"
    assert next(task for task in saved.tasks if task.task_id == SHARED_CV).status == "completed"
    assert any(task.waiting_for for task in saved.tasks if task.task_id.startswith("oist-fall-2027/"))
    assert not any(task.task_id.startswith("epfl-summer-2027/reference") for task in saved.tasks)
    accepted = store.accept_plan(plan.id)
    assert accepted.status == "accepted"
    oist = store.get_opportunity("oist-fall-2027")
    impact = store.upsert_opportunity(set_fact(oist, "reference_min", 2))
    revised = build_plan(store.context(selected), profile, previous=accepted, impact=impact)
    assert impact.affected_target_ids == [oist.id]
    assert SHARED_CV in impact.preserved_task_ids
    assert next(task for task in revised.tasks if task.task_id == SHARED_CV).status == "completed"
    assert next(task for task in revised.tasks if task.task_id.endswith("/reference-receipt/v1")).status == "waiting"
    assert store.save_plan(revised).id == revised.id


def test_new_hard_requirement_invalidates_only_affected_target_and_rejects_acceptance(store):
    epfl = opportunity()
    oist = opportunity("oist-test-2027", references=1)
    store.upsert_opportunity(epfl)
    store.upsert_opportunity(oist)
    context = store.context([epfl.id, oist.id])
    guard_key = f"{oist.id}/requirement_set"
    old_guard = context.fact_versions[guard_key]
    assert all(fact.name != "requirement_set" for target in context.opportunities for fact in target.facts)
    assert all("requirement_set" not in task.fact_names for task in context.tasks)
    prior = proposal(store, [epfl.id, oist.id])
    store.save_plan(prior)
    updated = oist.model_copy(deep=True)
    updated.facts.append(Fact(name="novel_hard_condition", value=True, status="known", kind="requirement",
                              excerpt="Applicants must satisfy this newly discovered condition.", source_url=oist.source_url))
    impact = store.upsert_opportunity(updated)
    assert [change.fact_name for change in impact.changes] == ["novel_hard_condition", "requirement_set"]
    assert impact.affected_plan_ids == [prior.id]
    assert impact.affected_target_ids == [oist.id]
    assert impact.affected_task_ids == []
    assert SHARED_CV in impact.preserved_task_ids
    assert f"{epfl.id}/statement-final/v1" in impact.preserved_task_ids
    assert any(old_guard in path.nodes and path.target_id == oist.id for path in impact.paths)
    assert store.get_plan(prior.id).status == "stale"
    with pytest.raises(StalePlanError):
        store.accept_plan(prior.id)
    current = store.context([epfl.id, oist.id])
    assert current.fact_versions[guard_key] != old_guard
    assert current.fact_versions[f"{epfl.id}/requirement_set"] == context.fact_versions[f"{epfl.id}/requirement_set"]
    guard_rows = store._graph.ro_query(
        "MATCH (guard:Fact {id:$guard})-[:CURRENT]->(v:FactVersion)-[:DERIVED_FROM]->(meta:GraphMetadata) "
        "RETURN guard.provenance, v.provenance, meta.provenance", params={"guard": guard_key},
    ).result_set
    assert guard_rows == [["graph_metadata", "graph_metadata", "graph_metadata"]]
    metadata_view = store.graph_view([oist.id])
    assert any(node["type"] == "GraphMetadata" for node in metadata_view["nodes"])


def test_new_information_fact_does_not_change_requirement_membership_or_stale_plan(store):
    target = opportunity()
    store.upsert_opportunity(target)
    prior = proposal(store, [target.id])
    old_guard = prior.fact_versions[f"{target.id}/requirement_set"]
    store.save_plan(prior)
    updated = target.model_copy(deep=True)
    updated.facts.append(Fact(name="funding", value=["travel"], status="known", kind="information",
                              excerpt="Travel support is available.", source_url=target.source_url))
    impact = store.upsert_opportunity(updated)
    assert [change.fact_name for change in impact.changes] == ["funding"]
    assert impact.affected_target_ids == [] and impact.affected_task_ids == [] and impact.affected_plan_ids == []
    assert store.context([target.id]).fact_versions[f"{target.id}/requirement_set"] == old_guard
    assert store.accept_plan(prior.id).status == "accepted"


def test_unguarded_legacy_plan_cannot_be_accepted(store):
    target = opportunity()
    store.upsert_opportunity(target)
    prior = proposal(store, [target.id])
    store.save_plan(prior)
    store._graph.query(
        "MATCH (p:Plan {id:$plan})-[:HAS_TARGET]->(target:PlanTarget)-[used:USED_FACT]->(v:FactVersion) "
        "WHERE v.name='requirement_set' DELETE used", params={"plan": prior.id},
    )
    with pytest.raises(StalePlanError):
        store.accept_plan(prior.id)
    updated = target.model_copy(deep=True)
    updated.facts.append(Fact(name="fresh_condition", value=True, status="known", kind="requirement",
                              excerpt="A new condition is mandatory.", source_url=target.source_url))
    impact = store.upsert_opportunity(updated)
    assert impact.affected_target_ids == [target.id] and impact.affected_plan_ids == [prior.id]


def test_acceptance_query_checks_current_guard_even_if_side_stale_flags_reset(store):
    target = opportunity()
    store.upsert_opportunity(target)
    prior = proposal(store, [target.id])
    store.save_plan(prior)
    updated = target.model_copy(deep=True)
    updated.facts.append(Fact(name="new_requirement", value=True, status="known", kind="requirement",
                              excerpt="This new requirement is mandatory.", source_url=target.source_url))
    store.upsert_opportunity(updated)
    store._graph.query("MATCH (plan:Plan {id:$plan}) SET plan.stale=false", params={"plan": prior.id})
    # Invoke the vetted write directly to prove the atomic database check, not
    # merely the earlier Python comparison or persisted side staleness flag.
    rows = store._run("accept_plan.cypher", {"plan_id": prior.id, "accepted_at": "2026-10-16T00:00:00Z"}, write=True)
    assert rows == []
    assert store._graph.ro_query("MATCH (p:Plan {id:$plan}) RETURN p.lifecycle_status",
                                params={"plan": prior.id}).result_set == [["proposed"]]


def test_acceptance_refuses_membership_not_reflected_by_guard_or_incomplete_recipes(store):
    target = opportunity()
    store.upsert_opportunity(target)
    prior = proposal(store, [target.id])
    store.save_plan(prior)
    store._graph.query(
        "MATCH (o:Opportunity {id:$target}) CREATE (f:Fact {id:$fact_id, name:'interrupted_requirement', "
        "provenance:'source_fact'}), (v:FactVersion {id:$version_id, kind:'requirement'}) "
        "CREATE (o)-[:HAS_FACT]->(f)-[:CURRENT]->(v)",
        params={"target": target.id, "fact_id": f"{target.id}/interrupted_requirement",
                "version_id": f"{target.id}/interrupted_requirement@temporary"},
    )
    with pytest.raises(StalePlanError):
        store.accept_plan(prior.id)
    store._graph.query("MATCH (o:Opportunity {id:$target}) SET o.recipe_ready=false", params={"target": target.id})
    with pytest.raises(StalePlanError):
        store.accept_plan(prior.id)


def test_requirement_membership_ignores_values_and_excludes_information():
    target = opportunity()
    guard = requirement_set(target)
    changed_value = set_fact(target, "reference_min", 2)
    assert requirement_set(changed_value).version_id == guard.version_id
    info = target.model_copy(deep=True)
    info.facts.append(Fact(name="funding", kind="information", status="unknown"))
    assert requirement_set(info).version_id == guard.version_id
    new_hard = target.model_copy(deep=True)
    new_hard.facts.append(Fact(name="previously_unseen", kind="requirement", status="unknown"))
    assert requirement_set(new_hard).version_id != guard.version_id
