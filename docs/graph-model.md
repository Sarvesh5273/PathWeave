# Implemented graph model

[Certain] This describes the implemented graph, recipes, planner and checked-in Cypher queries.

## Stored nodes and edges

| Nodes | Stored purpose and connections |
| --- | --- |
| `Opportunity` | Program/cohort identity, call state and source metadata; `HAS_FACT → Fact`, `REQUIRES → Deliverable`. |
| `Fact`, `FactVersion` | Scoped fact identity and immutable semantic versions; `Fact -CURRENT→ FactVersion`. Versions keep kind, known/unknown/conflicting status and value. |
| `Source` | A dated source observation, mode, snapshot state and payload; `FactVersion -SUPPORTED_BY→ Source` carries the supporting excerpt. |
| `Deliverable`, `PrepTask` | Target-specific outputs and authored work; `PrepTask -SUPPORTS→ Deliverable`, `DEPENDS_ON → PrepTask`, `USES_FACT → Fact`. |
| `Plan`, `PlanTarget`, `PlanTask` | Immutable proposal payload and saved decisions; `Plan -HAS_TARGET→ PlanTarget`, `HAS_TASK → PlanTask`. Decisions `USED_FACT → FactVersion`; saved tasks retain `DEPENDS_ON` edges. |
| `GraphMetadata` | Internal requirement-membership definition; the `requirement_set` version `DERIVED_FROM → GraphMetadata`. |

Criterion results and artifact types live in payloads, not separate graph nodes.

## Evidence, estimates and guards

Official facts retain URLs, excerpts and checked observations. Version identity includes opportunity, fact name, kind, status and canonicalized value. Formatting alone does not change identity; retrieval failure makes context uncertain.

Tasks carry `planner_estimate:explicit_recipe_v1`: authored estimates and dependencies, not official required hours. Only CV and transcript bases share identities; final documents remain target scoped. Recommendation receipt requires an observed synthetic event, never requested letters or elapsed time.

The `requirement_set` guard records hard-requirement names/kinds with `graph_metadata` provenance. It catches newly added requirements absent from older plans; no source excerpt is invented.

## Essential query mapping

| Query | Product behavior |
| --- | --- |
| `prerequisite_closure.cypher` | Traverses target → deliverable ← supporting task → prerequisites, returning reusable task identities and actual paths. |
| `context_evidence.cypher` | Extends preparation paths through current facts to supporting observations/excerpts. |
| `impact_targets.cypher` | Finds saved target decisions using replaced fact versions and marks them stale. |
| `impact_tasks.cypher` | Traverses saved task prerequisites to replaced versions; marks affected work and returns evidence paths. |
| `impact_unguarded_targets.cypher` | Invalidates legacy decisions missing the requirement-membership guard. |
| `accept_plan.cypher` | Rejects stale/incomplete proposals, missing guards or changed dependencies before persisting acceptance. |

[Certain] Python consumes graph-returned context to evaluate criteria and allocate one budget, using effort upper bounds, prerequisite ordering and exam protection. A failed allocation is at risk; infeasibility requires a lower-bound shortfall against optimistic capacity. Missing facts, portal certainty or receipt prevent certification.

## Why FalkorDB is central

The graph supplies prerequisite closure, shared identities, source dependency impact and acceptance checks. Outages return no substitute graph result. Reference-count simulation changes the affected target and its request, receipt and application-review tasks; compatible shared CV survives. Deterministic code reschedules from that context. Simulation uses a separate FalkorDB graph.
