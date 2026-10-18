"""FalkorDB storage and fixed graph tools for preparation and selective repair.

No tool accepts Cypher or a graph name from the model. Fact versions are semantic;
source observations and immutable plan bodies preserve evidence and history.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from falkordb import FalkorDB
from redis.exceptions import RedisError

from app.config import Settings, settings as default_settings
from app.models import (
    ChangeImpact,
    EvidencePath,
    Fact,
    FactChange,
    GraphContext,
    Opportunity,
    Plan,
    PreparationTask,
    SourceSnapshot,
    TopicInfo,
    utc_now,
)
from app.recipes import recipes_for
from app.topics import catalog_rows, fact_topic_links, prerequisite_closure, topic_keys_for


QUERY_DIR = Path(__file__).resolve().parents[1] / "queries"
MAX_FACTS = 64
REQUIREMENT_SET = "requirement_set"
MAX_PLAN_FACTS = (MAX_FACTS + 1) * 3
MAX_SELECTED = 3
MAX_TASKS = 192
MAX_TOPICS = 64
MAX_PATH_ROWS = 1000
MAX_VIEW_NODES = 160
MAX_VIEW_EDGES = 240
SET_FACTS = {"documents", "degree_levels", "fields", "funding"}
_LOCKS: dict[tuple[str, int, str], threading.RLock] = {}
_LOCK_GUARD = threading.Lock()


class GraphUnavailable(RuntimeError):
    """Safe database failure; provider messages and credentials are not returned."""


class GraphIntegrityError(ValueError):
    """Stored context exceeds the bounded contract or has inconsistent identities."""


class StalePlanError(ValueError):
    """A proposal's dependencies are no longer current."""


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _canonical_value(name: str, value: Any) -> Any:
    if name in SET_FACTS and isinstance(value, list):
        return [json.loads(item) for item in sorted({_json(item) for item in value})]
    return value


def fact_version_id(opportunity_id: str, fact: Fact) -> str:
    """Identity includes the fact scope; unrelated equal values never share a version."""
    semantic = {"status": fact.status, "kind": fact.kind, "value": _canonical_value(fact.name, fact.value)}
    return f"{opportunity_id}/{fact.name}@{_hash(semantic)[:24]}"


def requirement_set(opportunity: Opportunity) -> Fact:
    """Track requirement membership without pretending it is a sourced condition.

    Existing fact values keep their own versioned dependencies. This guard changes
    only when the set of hard requirement names/kinds changes, covering rules an
    earlier assessment could not reference because they did not yet exist.
    """
    guard = Fact(name=REQUIREMENT_SET, kind="information", status="known", value=sorted(
        ({"name": fact.name, "kind": fact.kind} for fact in opportunity.facts if fact.kind == "requirement"),
        key=lambda row: row["name"],
    ))
    guard.version_id = fact_version_id(opportunity.id, guard)
    return guard


class GraphStore:
    def __init__(self, settings: Settings = default_settings):
        if not re.fullmatch(r"[A-Za-z0-9_:-]{1,128}", settings.db_graph):
            raise ValueError("Invalid server-configured graph name.")
        self.settings = settings
        self._client: FalkorDB | None = None
        self._graph = None
        self._initialized = False
        key = (settings.db_host, settings.db_port, settings.db_graph)
        with _LOCK_GUARD:
            self._lock = _LOCKS.setdefault(key, threading.RLock())

    def _db(self) -> FalkorDB:
        if self._client is None:
            try:
                self._client = FalkorDB(
                    host=self.settings.db_host,
                    port=self.settings.db_port,
                    password=self.settings.db_password,
                    ssl=self.settings.db_ssl,
                    socket_connect_timeout=3,
                    socket_timeout=max(5, self.settings.query_timeout_ms / 1000 + 2),
                )
                self._graph = self._client.select_graph(self.settings.db_graph)
            except RedisError as exc:
                raise GraphUnavailable("FalkorDB is unavailable; no in-memory graph result was substituted.") from exc
        return self._client

    def _exists(self) -> bool:
        try:
            return self.settings.db_graph in self._db().list_graphs()
        except RedisError as exc:
            raise GraphUnavailable("FalkorDB is unavailable; stored graph state could not be read.") from exc

    def _run(self, filename: str, params: dict[str, Any] | None = None, *, write=False) -> list[list[Any]]:
        self._db()
        query = (QUERY_DIR / filename).read_text(encoding="utf-8")
        try:
            method = self._graph.query if write else self._graph.ro_query
            return method(query, params=params or {}, timeout=self.settings.query_timeout_ms).result_set
        except RedisError as exc:
            raise GraphUnavailable("FalkorDB query failed; no substitute graph result was returned.") from exc

    def _ensure(self):
        if not self._initialized:
            self._run("initialize.cypher", write=True)
            self._initialized = True

    def health(self) -> dict:
        try:
            with self._lock:
                client = self._db()
                ready = bool(client.connection.ping())
                return {
                    "status": "ok" if ready else "unavailable",
                    "database": "FalkorDB",
                    "graph": self.settings.db_graph,
                    "initialized": self._exists(),
                }
        except (GraphUnavailable, RedisError):
            return {"status": "unavailable", "database": "FalkorDB", "graph": self.settings.db_graph}

    @staticmethod
    def _validate_id(value: str, label: str):
        if not isinstance(value, str) or not value or len(value) > 240 or any(ord(char) < 32 for char in value):
            raise ValueError(f"Invalid {label}.")

    def _normalize_opportunity(self, incoming: Opportunity, previous: Opportunity | None) -> Opportunity:
        self._validate_id(incoming.id, "opportunity ID")
        if not incoming.facts:
            raise ValueError("Opportunity facts must include explicit unknowns when extraction is incomplete.")
        names = [fact.name for fact in incoming.facts]
        if len(names) != len(set(names)) or len(names) > MAX_FACTS:
            raise ValueError("Opportunity facts must have unique names and fit the bounded fact limit.")
        result = incoming.model_copy(deep=True)
        before = {fact.name: fact for fact in previous.facts} if previous is not None else {}
        for fact in result.facts:
            if fact.name == REQUIREMENT_SET:
                raise ValueError("requirement_set is reserved for graph-derived metadata.")
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", fact.name):
                raise ValueError("Fact names must be canonical identifiers.")
            old = before.get(fact.name)
            if old is not None and fact.status == "unknown" and not fact.excerpt.strip():
                # A placeholder records extraction failure, not a repeal or downgrade
                # of the formerly observed rule. Keep its historical context.
                fact.kind = old.kind
                fact.value = old.value
                fact.excerpt = old.excerpt
                fact.source_url = old.source_url
                fact.source_id = old.source_id
            fact.value = _canonical_value(fact.name, fact.value)
            fact.source_url = fact.source_url or result.source_url
            if fact.status == "known" and (not fact.excerpt.strip() or not fact.source_url):
                fact.status = "unknown"
            fact.source_id = fact.source_id or f"source-{_hash(fact.source_url)[:16]}"
            fact.version_id = fact_version_id(result.id, fact)
        if previous is not None:
            for old in previous.facts:
                if old.name in names:
                    continue
                retained = old.model_copy(deep=True)
                retained.status = "unknown"
                retained.version_id = fact_version_id(result.id, retained)
                result.facts.append(retained)
            if len(result.facts) > MAX_FACTS:
                raise ValueError("Merged opportunity exceeds the bounded fact limit.")
        result.facts.sort(key=lambda fact: fact.name)
        portal = next((f for f in result.facts if f.name == "portal_status"), None)
        if portal is not None:
            result.call_status = (
                portal.value if portal.status == "known" and isinstance(portal.value, str)
                and portal.value in {"open", "closed", "future"}
                else "unknown"
            )
        deadline = next((f for f in result.facts if f.name == "application_deadline"), None)
        if deadline is not None and deadline.status == "known" and isinstance(deadline.value, str):
            try:
                date = datetime.fromisoformat(deadline.value.replace("Z", "+00:00"))
            except ValueError:
                date = None
            if date is not None and date.tzinfo is not None and date < datetime.now(timezone.utc):
                result.call_status = "closed"
        if any(f.status == "conflicting" for f in result.facts):
            result.verification = "uncertain"
        return result

    def _fact_rows(self, opportunity: Opportunity, snapshot: SourceSnapshot | None, *, source_failed=False) -> list[dict]:
        rows = []
        for fact in opportunity.facts:
            actual = snapshot if snapshot is not None and snapshot.url == fact.source_url else None
            checked_at = actual.checked_at if actual is not None else opportunity.checked_at
            mode = actual.mode if actual is not None else opportunity.mode
            state = "failed" if source_failed else "observed" if actual is not None else "excerpt_only"
            if actual is not None:
                source_payload = actual.model_dump(mode="json")
                source_payload["content_hash"] = actual.content_hash or _hash(actual.text)
            else:
                source_payload = SourceSnapshot(
                    id=fact.source_id, url=fact.source_url, checked_at=checked_at, mode=mode,
                ).model_dump(mode="json")
            observation = {
                "url": fact.source_url, "checked_at": checked_at, "mode": mode,
                "content_hash": source_payload.get("content_hash", ""),
            }
            source_node_id = f"source/{_hash(fact.source_url)[:16]}/{_hash(observation)[:20]}"
            rows.append({
                "id": f"{opportunity.id}/{fact.name}", "name": fact.name,
                "version_id": fact.version_id, "payload": _json(fact.model_dump(mode="json")),
                "status": fact.status, "kind": fact.kind, "value_json": _json(fact.value),
                "source_url": fact.source_url, "source_node_id": source_node_id,
                "source_payload": _json(source_payload), "source_checked_at": checked_at,
                "source_mode": mode, "source_state": state,
                "has_snapshot": actual is not None, "excerpt": fact.excerpt,
            })
        return rows

    def upsert_opportunity(self, opportunity: Opportunity, snapshot: SourceSnapshot | None = None) -> ChangeImpact:
        return self._upsert_opportunity(opportunity, snapshot)

    def _upsert_opportunity(self, opportunity: Opportunity, snapshot: SourceSnapshot | None = None,
                            *, source_failed=False) -> ChangeImpact:
        with self._lock:
            self._ensure()
            previous = self.get_opportunity(opportunity.id)
            normalized = self._normalize_opportunity(opportunity, previous)
            before = {fact.name: fact for fact in previous.facts} if previous is not None else {}
            previous_guards = self._run("requirement_sets.cypher", {"selected_ids": [opportunity.id]})
            if previous_guards:
                before[REQUIREMENT_SET] = Fact.model_validate_json(previous_guards[0][3])
            guard = requirement_set(normalized)
            rows = self._run("upsert_opportunity.cypher", {
                "opportunity_id": normalized.id,
                "opportunity_payload": _json(normalized.model_dump(mode="json")),
                "program": normalized.program,
                "source_url": normalized.source_url,
                "checked_at": normalized.checked_at,
                "facts": self._fact_rows(normalized, snapshot, source_failed=source_failed),
            }, write=True)
            rows.extend(self._run("upsert_requirement_set.cypher", {
                "opportunity_id": normalized.id,
                "requirement_set": self._requirement_set_row(normalized.id, guard),
                "checked_at": normalized.checked_at,
            }, write=True))
            after = {fact.name: fact for fact in normalized.facts}
            after[REQUIREMENT_SET] = guard
            changes = []
            for fact_id, old_version, new_version in rows:
                if old_version == new_version:
                    continue
                name = fact_id[len(normalized.id) + 1:]
                old = before.get(name)
                changes.append(FactChange(
                    opportunity_id=normalized.id, fact_name=name,
                    old_version_id=old_version, new_version_id=new_version,
                    old_value=old.value if old else None, new_value=after[name].value,
                ))
            self._write_recipes(normalized)
            return self._impact(changes)

    @staticmethod
    def _requirement_set_row(opportunity_id: str, guard: Fact) -> dict:
        return {
            "id": f"{opportunity_id}/{REQUIREMENT_SET}", "version_id": guard.version_id,
            "payload": _json(guard.model_dump(mode="json")), "value_json": _json(guard.value),
            "names": [row["name"] for row in guard.value],
        }

    def _write_recipes(self, opportunity: Opportunity):
        bundle = recipes_for(opportunity)
        self._run("reset_recipe_edges.cypher", {"opportunity_id": opportunity.id}, write=True)
        self._run("upsert_prep_tasks.cypher", {"tasks": [
            {
                "id": task.id, "title": task.title, "payload": _json(task.model_dump(mode="json")),
                "fact_names": task.fact_names, "provenance": task.provenance,
            } for task in bundle.tasks
        ]}, write=True)
        dependencies = [
            {"task_id": task.id, "prerequisite_id": dependency}
            for task in bundle.tasks for dependency in task.dependencies
        ]
        if dependencies:
            self._run("prep_dependencies.cypher", {"dependencies": dependencies}, write=True)
        fact_names = {fact.name for fact in opportunity.facts}
        links = [
            {"task_id": task.id, "fact_id": f"{opportunity.id}/{name}"}
            for task in bundle.tasks for name in task.fact_names if name in fact_names
        ]
        if links:
            self._run("prep_fact_links.cypher", {"links": links}, write=True)
        self._run("upsert_deliverables.cypher", {"opportunity_id": opportunity.id, "deliverables": [
            {"id": d.id, "name": d.name, "task_id": d.task_id, "provenance": d.provenance}
            for d in bundle.deliverables
        ]}, write=True)
        self._write_topics(opportunity)
        self._run("recipe_ready.cypher", {"opportunity_id": opportunity.id}, write=True)

    def _write_topics(self, opportunity: Opportunity) -> None:
        """Idempotently map current sourced facts to the reviewed topic graph."""
        self._run("reset_topic_fact_links.cypher", {"prefix": f"{opportunity.id}/"}, write=True)
        keys = prerequisite_closure(topic_keys_for(opportunity))
        if not keys:
            return
        rows = catalog_rows(keys)
        self._run("upsert_topics.cypher", {"topics": [
            {"key": topic["key"], "title": topic["title"], "family": topic["family"],
             "payload": _json(topic)}
            for topic in rows["topics"]
        ]}, write=True)
        if rows["resources"]:
            self._run("upsert_topic_resources.cypher", {"resources": rows["resources"]}, write=True)
        if rows["edges"]:
            self._run("topic_prerequisite_edges.cypher", {"edges": rows["edges"]}, write=True)
        links = fact_topic_links(opportunity)
        if links:
            self._run("topic_fact_links.cypher", {"links": links}, write=True)

    def backfill_topics(self) -> int:
        """Map saved source facts into the topic graph without provider calls."""
        with self._lock:
            opportunities = self.list_opportunities()
            for opportunity in opportunities:
                self._write_topics(opportunity)
            return len(opportunities)

    @staticmethod
    def _opportunity(row: list[Any]) -> Opportunity:
        opportunity = Opportunity.model_validate_json(row[0])
        opportunity.facts = sorted((Fact.model_validate_json(item) for item in row[1] if item), key=lambda f: f.name)
        return opportunity

    def list_opportunities(self) -> list[Opportunity]:
        with self._lock:
            if not self._exists():
                return []
            return [self._opportunity(row) for row in self._run("list_opportunities.cypher")]

    def get_opportunity(self, opportunity_id: str) -> Opportunity | None:
        self._validate_id(opportunity_id, "opportunity ID")
        with self._lock:
            if not self._exists():
                return None
            rows = self._run("get_opportunity.cypher", {"opportunity_id": opportunity_id})
            return self._opportunity(rows[0]) if rows else None

    def context(self, selected_ids: list[str]) -> GraphContext:
        if len(selected_ids) > MAX_SELECTED or len(set(selected_ids)) != len(selected_ids):
            raise ValueError("Select at most three distinct opportunities.")
        with self._lock:
            if not selected_ids:
                return GraphContext()
            opportunities = []
            for opportunity_id in selected_ids:
                opportunity = self.get_opportunity(opportunity_id)
                if opportunity is None:
                    raise ValueError(f"Unknown opportunity ID: {opportunity_id}")
                rows = self._run("get_opportunity.cypher", {"opportunity_id": opportunity_id})
                if not rows[0][2]:
                    raise GraphIntegrityError("Preparation graph update is incomplete; retry source ingestion.")
                opportunities.append(opportunity)
            params = {"selected_ids": selected_ids}
            if self._run("prerequisite_overflow.cypher", params):
                raise GraphIntegrityError("Prerequisite graph exceeds the vetted traversal depth of eight.")
            rows = self._run("prerequisite_closure.cypher", params)
            if len(rows) > MAX_PATH_ROWS:
                raise GraphIntegrityError("Prerequisite paths exceed the bounded context limit.")
            tasks: dict[str, PreparationTask] = {}
            evidence: list[EvidencePath] = []
            for target_id, task_id, payload, nodes, relationships, dependencies in rows:
                if not payload:
                    raise GraphIntegrityError("A graph prerequisite has no preparation recipe.")
                if task_id not in tasks:
                    tasks[task_id] = PreparationTask.model_validate_json(payload)
                    tasks[task_id].dependencies = sorted({d for d in dependencies if d})
                    tasks[task_id].target_ids = []
                if target_id not in tasks[task_id].target_ids:
                    tasks[task_id].target_ids.append(target_id)
                evidence.append(EvidencePath(
                    target_id=target_id, task_id=task_id, nodes=nodes,
                    relationship=" > ".join(relationships),
                ))
            if len(tasks) > MAX_TASKS:
                raise GraphIntegrityError("Preparation tasks exceed the bounded context limit.")
            deadline_by_id = {o.id: next((f.value for f in o.facts if f.name == "application_deadline"
                                        and f.status == "known"), None) for o in opportunities}
            for task in tasks.values():
                dates = []
                for target_id in task.target_ids:
                    value = deadline_by_id.get(target_id)
                    if not isinstance(value, str):
                        continue
                    try:
                        deadline = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    except ValueError:
                        continue
                    if deadline.tzinfo is not None:
                        dates.append(deadline)
                task.due_at = min(dates).isoformat() if dates else None
                task.target_ids.sort()
            evidence_rows = self._run("context_evidence.cypher", params)
            if len(evidence_rows) > MAX_PATH_ROWS:
                raise GraphIntegrityError("Evidence paths exceed the bounded context limit.")
            evidence.extend(EvidencePath(
                target_id=row[0], task_id=row[1], nodes=row[2],
                relationship=" > ".join(row[3]), source_url=row[4] or "", excerpt=row[5] or "",
            ) for row in evidence_rows)
            guards = self._run("requirement_sets.cypher", {"selected_ids": selected_ids})
            # A legacy stored opportunity can receive this metadata without
            # re-fetching or rewriting its official source observations.
            guarded_ids = {row[0] for row in guards}
            for opportunity in opportunities:
                if opportunity.id in guarded_ids:
                    continue
                guard = requirement_set(opportunity)
                rows = self._run("upsert_requirement_set.cypher", {
                    "opportunity_id": opportunity.id,
                    "requirement_set": self._requirement_set_row(opportunity.id, guard),
                    "checked_at": utc_now(),
                }, write=True)
                self._impact([FactChange(
                    opportunity_id=opportunity.id, fact_name=REQUIREMENT_SET,
                    old_version_id=rows[0][1], new_version_id=rows[0][2], new_value=guard.value,
                )])
            guards = self._run("requirement_sets.cypher", {"selected_ids": selected_ids})
            versions = {f"{o.id}/{f.name}": f.version_id for o in opportunities for f in o.facts}
            versions.update({row[1]: row[2] for row in guards})
            return GraphContext(
                opportunities=opportunities,
                tasks=sorted(tasks.values(), key=lambda task: task.id),
                evidence=self._unique_paths(evidence),
                fact_versions=versions,
                topics=self._topics(selected_ids),
            )

    def _topics(self, selected_ids: list[str]) -> list[TopicInfo]:
        rows = self._run("topic_fact_map.cypher", {"selected_ids": selected_ids})
        if not rows:
            return []
        closure = self._run("topic_prereq_closure.cypher", {"selected_ids": selected_ids})
        if len(closure) > MAX_TOPICS:
            raise GraphIntegrityError("Learning topic closure exceeds the bounded context limit.")
        topics: dict[str, TopicInfo] = {}
        for key, payload in closure:
            if key in topics:
                continue
            data: dict[str, Any] = {}
            if payload:
                try:
                    parsed = json.loads(payload)
                    if isinstance(parsed, dict):
                        data = parsed
                except ValueError:
                    data = {}
            topics[key] = TopicInfo(
                key=key, title=str(data.get("title", "")), family=str(data.get("family", "")),
                prerequisites=[item for item in data.get("prerequisites", []) if isinstance(item, str)],
                resources=[item for item in data.get("resources", [])
                           if isinstance(item, dict) and isinstance(item.get("title"), str)
                           and isinstance(item.get("url"), str)],
            )
        for target_id, fact_id, key, _payload in rows:
            topic = topics.get(key)
            if topic is None:
                continue
            name = fact_id[len(target_id) + 1:] if fact_id.startswith(f"{target_id}/") else fact_id
            names = topic.required_by.setdefault(target_id, [])
            if name not in names:
                names.append(name)
        for topic in topics.values():
            for names in topic.required_by.values():
                names.sort()
        return [topics[key] for key in sorted(topics)]

    @staticmethod
    def _unique_paths(paths: list[EvidencePath]) -> list[EvidencePath]:
        unique = {}
        for path in paths:
            key = (path.target_id, path.task_id, tuple(path.nodes), path.excerpt)
            unique.setdefault(key, path)
        return list(unique.values())

    def _impact(self, changes: list[FactChange]) -> ChangeImpact:
        impact = ChangeImpact(changes=sorted(changes, key=lambda c: (c.opportunity_id, c.fact_name)),
                              semantic_change=bool(changes))
        old_versions = sorted({c.old_version_id for c in changes if c.old_version_id})
        rows = self._run("impact_targets.cypher", {"old_version_ids": old_versions}, write=True) if old_versions else []
        task_rows = self._run("impact_tasks.cypher", {"old_version_ids": old_versions}, write=True) if old_versions else []
        guard_targets = sorted({c.opportunity_id for c in changes if c.fact_name == REQUIREMENT_SET})
        if guard_targets:
            rows.extend(self._run("impact_unguarded_targets.cypher", {"opportunity_ids": guard_targets}, write=True))
        if len(rows) > MAX_PATH_ROWS or len(task_rows) > MAX_PATH_ROWS:
            raise GraphIntegrityError("Fact impact exceeds the bounded result limit; dependent plans were marked stale.")
        all_rows = rows + task_rows
        impact.affected_plan_ids = sorted({row[0] for row in all_rows})
        impact.affected_target_ids = sorted({row[1] for row in all_rows if row[1]})
        impact.affected_task_ids = sorted({row[2] for row in all_rows if row[2]})
        impact.paths = self._unique_paths([EvidencePath(
            target_id=row[1] or "", task_id=row[2] or "", nodes=row[3],
            relationship=" > ".join(row[6]),
            source_url=row[4] or "", excerpt=row[5] or "",
        ) for row in all_rows])
        if impact.affected_plan_ids:
            tasks = self._run("plan_task_ids.cypher", {"plan_ids": impact.affected_plan_ids})
            if len(tasks) > MAX_TASKS:
                raise GraphIntegrityError("Affected plans exceed the bounded task result limit.")
            impact.preserved_task_ids = sorted({row[0] for row in tasks} - set(impact.affected_task_ids))
        return impact

    def _current_versions(self, keys: list[str]) -> dict[str, str]:
        if not keys:
            return {}
        return dict(self._run("current_versions.cypher", {"fact_ids": keys}))

    def save_plan(self, plan: Plan) -> Plan:
        self._validate_id(plan.id, "plan ID")
        if plan.status != "proposed":
            raise ValueError("Save a proposal, then use accept_plan to accept it.")
        if not plan.selected_ids or len(plan.selected_ids) > MAX_SELECTED or len(set(plan.selected_ids)) != len(plan.selected_ids):
            raise ValueError("A plan needs one to three distinct selected opportunities.")
        if len(plan.tasks) > MAX_TASKS or len(plan.fact_versions) > MAX_PLAN_FACTS:
            raise ValueError("Plan exceeds the bounded storage contract.")
        if len({t.task_id for t in plan.tasks}) != len(plan.tasks):
            raise ValueError("Plan task IDs must be distinct.")
        if {target.target_id for target in plan.targets} != set(plan.selected_ids):
            raise ValueError("Plan target assessments must match selected opportunities.")
        task_ids = {task.task_id for task in plan.tasks}
        if any(set(task.dependencies) - task_ids for task in plan.tasks):
            raise ValueError("Plan dependencies must name tasks in the same plan.")
        valid_prefixes = tuple(f"{target}/" for target in plan.selected_ids)
        if any(not key.startswith(valid_prefixes) for key in plan.fact_versions):
            raise ValueError("Plan facts must belong to its selected opportunities.")
        with self._lock:
            self._ensure()
            for opportunity_id in plan.selected_ids:
                if self.get_opportunity(opportunity_id) is None:
                    raise ValueError("A selected opportunity is absent from graph storage.")
                if f"{opportunity_id}/{REQUIREMENT_SET}" not in plan.fact_versions:
                    raise ValueError("Plan is missing the graph requirement-set guard; rebuild from current context.")
            versions = set(plan.fact_versions.values())
            found = dict(self._run("version_ids.cypher", {"version_ids": sorted(versions)})) if versions else {}
            if set(found) != versions or any(found.get(version) != key for key, version in plan.fact_versions.items()):
                raise ValueError("Plan includes unrecognized fact versions.")
            if any(set(task.fact_version_ids) - versions for task in plan.tasks):
                raise ValueError("Plan tasks may use only recorded plan fact versions.")
            if any(set(target.used_fact_versions) - versions for target in plan.targets):
                raise ValueError("Plan target assessments may use only recorded plan fact versions.")
            if any(found[version].rsplit("/", 1)[0] != target.target_id
                   for target in plan.targets for version in target.used_fact_versions):
                raise ValueError("Plan target facts must belong to that target.")
            payload = _json(plan.model_dump(mode="json"))
            rows = self._run("create_plan.cypher", {
                "plan_id": plan.id, "payload": payload, "profile_id": plan.profile.id,
                "created_at": plan.created_at,
            }, write=True)
            if rows[0][0] != payload:
                raise ValueError("A plan ID already has different immutable content; create a new proposal ID.")
            if rows[0][1]:
                return self.get_plan(plan.id)
            targets = []
            used_versions = set()
            for target in plan.targets:
                used = sorted(set(target.used_fact_versions)) if target.used_fact_versions else sorted(
                    version for key, version in plan.fact_versions.items() if key.startswith(f"{target.target_id}/"))
                used = sorted(set(used) | {plan.fact_versions[f"{target.target_id}/{REQUIREMENT_SET}"]})
                used_versions.update(used)
                targets.append({
                    "id": f"{plan.id}/target/{target.target_id}", "target_id": target.target_id,
                    "payload": _json(target.model_dump(mode="json")), "versions": used,
                })
            self._run("save_plan_targets.cypher", {"plan_id": plan.id, "targets": targets}, write=True)
            self._run("save_plan_tasks.cypher", {"plan_id": plan.id, "tasks": [
                {"id": f"{plan.id}/task/{task.task_id}", "task_id": task.task_id,
                 "target_ids": task.target_ids, "payload": _json(task.model_dump(mode="json")),
                 "versions": sorted(set(task.fact_version_ids))} for task in plan.tasks
            ]}, write=True)
            used_versions.update(version for task in plan.tasks for version in task.fact_version_ids)
            dependencies = [
                {"task_id": f"{plan.id}/task/{task.task_id}", "prerequisite_id": f"{plan.id}/task/{dependency}"}
                for task in plan.tasks for dependency in task.dependencies
            ]
            if dependencies:
                self._run("save_plan_dependencies.cypher", {"dependencies": dependencies}, write=True)
            used_facts = {found[version]: version for version in used_versions}
            stale = self._current_versions(list(used_facts)) != used_facts
            self._run("complete_plan.cypher", {"plan_id": plan.id, "stale": stale}, write=True)
            return self.get_plan(plan.id)

    def _plan(self, row: list[Any]) -> Plan:
        plan = Plan.model_validate_json(row[0])
        lifecycle = row[1] or "proposed"
        stale = bool(row[2])
        plan.status = "stale" if stale and lifecycle == "proposed" else lifecycle
        if stale:
            warning = "Stored plan facts have changed or are uncertain; review a new proposal before using this plan."
            if warning not in plan.warnings:
                plan.warnings.append(warning)
            items = self._run("plan_stale_items.cypher", {"plan_id": plan.id})
            plan.affected_target_ids = sorted({item[0] for item in items if item[0]})
            plan.affected_task_ids = sorted({item[1] for item in items if item[1]})
        return plan

    def get_plan(self, plan_id: str) -> Plan | None:
        self._validate_id(plan_id, "plan ID")
        with self._lock:
            if not self._exists():
                return None
            rows = self._run("get_plan.cypher", {"plan_id": plan_id})
            return self._plan(rows[0]) if rows else None

    def latest_plan(self, profile_id: str = "demo-student") -> Plan | None:
        self._validate_id(profile_id, "profile ID")
        with self._lock:
            if not self._exists():
                return None
            rows = self._run("latest_plan.cypher", {"profile_id": profile_id})
            return self._plan(rows[0]) if rows else None

    def accept_plan(self, plan_id: str) -> Plan:
        with self._lock:
            plan = self.get_plan(plan_id)
            if plan is None:
                raise ValueError("Unknown plan ID.")
            if any(f"{target_id}/{REQUIREMENT_SET}" not in plan.fact_versions for target_id in plan.selected_ids):
                raise StalePlanError("The stored proposal predates requirement-set guards; rebuild it before acceptance.")
            used_facts = dict(self._run("plan_used_versions.cypher", {"plan_id": plan_id}))
            if self._current_versions(list(used_facts)) != used_facts:
                raise StalePlanError("The proposal uses changed or uncertain facts; generate a new proposal before acceptance.")
            rows = self._run("accept_plan.cypher", {"plan_id": plan_id, "accepted_at": utc_now()}, write=True)
            if not rows:
                raise StalePlanError("The proposal became stale before acceptance; review a new proposal.")
            return self._plan(rows[0])

    def mark_source_uncertain(self, source_url: str) -> ChangeImpact:
        with self._lock:
            if not self._exists():
                return ChangeImpact()
            ids = self._run("source_opportunities.cypher", {"source_url": source_url})
            if len(ids) > 100:
                raise GraphIntegrityError("Source update exceeds the bounded opportunity limit.")
            parts = []
            for row in ids:
                opportunity = self.get_opportunity(row[0])
                if opportunity is None:
                    continue
                opportunity.checked_at = utc_now()
                opportunity.verification = "uncertain"
                for fact in opportunity.facts:
                    if fact.source_url == source_url:
                        fact.status = "unknown"
                parts.append(self._upsert_opportunity(opportunity, source_failed=True))
            return ChangeImpact(
                changes=[change for part in parts for change in part.changes],
                affected_plan_ids=sorted({p for part in parts for p in part.affected_plan_ids}),
                affected_target_ids=sorted({p for part in parts for p in part.affected_target_ids}),
                affected_task_ids=sorted({p for part in parts for p in part.affected_task_ids}),
                paths=self._unique_paths([path for part in parts for path in part.paths]),
                semantic_change=any(part.semantic_change for part in parts),
                preserved_task_ids=sorted({p for part in parts for p in part.preserved_task_ids}
                                          - {p for part in parts for p in part.affected_task_ids}),
            )

    def graph_view(self, selected_ids: list[str]) -> dict:
        if len(selected_ids) > MAX_SELECTED or len(set(selected_ids)) != len(selected_ids):
            raise ValueError("Graph view accepts at most three distinct opportunities.")
        with self._lock:
            if not selected_ids or not self._exists():
                return {"nodes": [], "edges": [], "truncated": False, "database": "FalkorDB"}
            for selected_id in selected_ids:
                self._validate_id(selected_id, "opportunity ID")
            rows = self._run("graph_view.cypher", {"selected_ids": selected_ids})
            fact_rows = self._run("graph_fact_view.cypher", {"selected_ids": selected_ids})
            guard_rows = self._run("graph_guard_view.cypher", {"selected_ids": selected_ids})
            truncated = len(rows) > 300 or len(fact_rows) > 192
            nodes: dict[str, dict] = {}
            edges: dict[tuple[str, str, str], dict] = {}
            for row in rows[:300] + fact_rows[:192] + guard_rows:
                path = row[0]
                id_map = {}
                for node in path.nodes():
                    props = node.properties
                    stable_id = props.get("id", str(node.id))
                    id_map[node.id] = stable_id
                    if stable_id not in nodes and len(nodes) < MAX_VIEW_NODES:
                        labels = node.labels
                        nodes[stable_id] = {
                            "id": stable_id,
                            "label": props.get("title") or props.get("name") or props.get("program") or stable_id,
                            "type": labels[0] if labels else "Node",
                            "provenance": props.get("provenance", ""),
                            "source_url": props.get("url") or props.get("source_url", ""),
                        }
                    elif stable_id not in nodes:
                        truncated = True
                for edge in path.edges():
                    source = id_map.get(edge.src_node)
                    target = id_map.get(edge.dest_node)
                    key = (source, target, edge.relation)
                    if source not in nodes or target not in nodes:
                        continue
                    if key not in edges and len(edges) < MAX_VIEW_EDGES:
                        edges[key] = {"source": source, "target": target, "type": edge.relation}
                    elif key not in edges:
                        truncated = True
            return {"nodes": list(nodes.values()), "edges": list(edges.values()),
                    "truncated": truncated, "database": "FalkorDB", "max_dependency_depth": 8}
