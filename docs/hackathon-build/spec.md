# Technical Spec

Status: implementation authorized. Shared contracts are in app/models.py.
Python 3.12, FastAPI, official FalkorDB client, static same-origin HTML/JS,
Groq local tool calling and TinyFish Search/Fetch.
Pinned database image: falkordb/falkordb:6.0.2; Python dependencies in pyproject.toml.

## Architecture and ownership

- Root: models.py, config.py, main.py, agent.py, static UI, integration scripts and docs.
- Graph agent: app/graph.py, app/recipes.py, queries/, tests/test_graph.py.
- Sources agent: app/sources.py, data/source_snapshots/, tests/test_sources.py.
- Planner agent: app/planner.py, tests/test_planner.py.
- Agents edit only owned paths, read full PRD/spec, and report contract conflicts.
- Root reviews changes and runs integration verification. No agent commits shared state.

## Graph Store — Epic 2/4/5

Class GraphStore(settings=settings).
Methods:
- health() -> dict
- upsert_opportunity(opportunity: Opportunity, snapshot: SourceSnapshot | None = None) -> ChangeImpact
- list_opportunities() -> list[Opportunity]
- get_opportunity(opportunity_id: str) -> Opportunity | None
- context(selected_ids: list[str]) -> GraphContext
- save_plan(plan: Plan) -> Plan
- get_plan(plan_id: str) -> Plan | None
- latest_plan(profile_id: str = "demo-student") -> Plan | None
- accept_plan(plan_id: str) -> Plan  (reject if dependent current fact versions changed)
- mark_source_uncertain(source_url: str) -> ChangeImpact
- graph_view(selected_ids: list[str]) -> dict  (bounded nodes/edges)

Graph contains Opportunity, Fact, FactVersion, Source, Deliverable, PrepTask, Plan,
PlanTarget and PlanTask; content may use JSON payload properties.
Fact.id = opportunity.id + "/" + fact.name. Version is deterministic hash of status,
value and kind; source refresh metadata excluded from semantic hash.
Fact-[:CURRENT]->FactVersion-[:SUPPORTED_BY]->Source.
Opportunity-[:HAS_FACT]->Fact.
Opportunity-[:REQUIRES]->Deliverable<-[:SUPPORTS]-PrepTask-[:DEPENDS_ON]->PrepTask.
PlanTarget/PlanTask-[:USED_FACT]->FactVersion; Plan-[:HAS_TARGET/HAS_TASK]->...
Plan JSON is immutable content; side status/staleness can change. Per-task USED_FACT
depends only on target facts relevant to that task. Common base work has planner origin.
context() must retrieve prerequisite closure and paths in Cypher, not assemble an
independent dependency traversal in Python. Bound depth to 8, depth constant in vetted query.
Source changes trace reverse USED_FACT relationships; only dependent target/tasks stale.
Missing source state invalidates certification, preserves prior versions/history.
Recipes are explicit team-authored preparation estimates, separate from official rules.

## Shared fact names — Epic 1/2

Adapters use:
- application_deadline: timezone-aware ISO string or unknown
- portal_status: open/closed/future/unknown
- documents: list of canonical names ("cv", "transcript", "statement", "reference", ...)
- reference_min: number; reference_received_before_submit: bool; reference_submitter: string
- statement_max_words: number; statement_max_chars: number
- transcript_translation: self/english_explanation/notarized/unknown
- fee_amount: number; fee_currency: string; funding: list/string
- degree_levels: list; fields: list; min_study_year: number; min_years_remaining: number
- institution_approval: bool; work_authorization_preference: string
Facts require excerpts; no inferred absence is a known false.
Opportunity.id must be program/cohort scoped: epfl-summer-2027, oist-fall-2027,
mitacs-summer-2027, google-fde-2027. Generic source IDs deterministic URL hash.

## Source Layer — Epic 1

TinyFishClient(settings=settings), methods search(query: str) -> dict,
fetch(urls: list[str]) -> list[SourceSnapshot].
DiscoverService(settings=settings), methods discover(query: str, limit: int=4) -> DiscoveryResult,
refresh(url: str) -> DiscoveryResult, load_examples() -> DiscoveryResult.
parse_snapshot(snapshot: SourceSnapshot) -> list[Opportunity].
Synchronous HTTP methods use bounded timeouts; FastAPI sync routes run in threadpool.
Read X-API-Key from configuration, never log it. No login/private pages.
Search uses real TinyFish REST; fetch chosen official public URLs and quote fragments.
Adapters extract exact supported fields; confidence is supported-known or unknown.
Generic unfamiliar pages yield source-linked partial cards, not invented full facts.
Examples saved from real public source snapshots are labeled cached with original checked_at.
Provider failure returns explicit errors. No silent live-to-cached replacement.
Snapshots exclude private data. Generic discovery limit <= 6; selected plan targets <= 3.
Sources can call existing TinyFish research tool to obtain seed snapshots, but deployed
app must independently make its own provider request in proof.
Endpoints documented at docs.tinyfish.ai/search-api/reference and fetch-api/reference.

## Planner — Epic 2/3

build_plan(context: GraphContext, profile: ProfileState, previous: Plan | None=None,
impact: ChangeImpact | None=None) -> Plan.
GraphContext tasks already contain graph-derived prerequisite closure and target links.
Planner cannot invent source requirements. Recipes have estimated hours and provenance.
Assess supported eligibility fields with typed rules, minimum versus preference.
Self-reported skill is not assessed competence.
Use weeks starting profile.start_date; exam_weeks are ISO Monday dates. Enforce shared
weekly budget and topological precedence. Unknown target deadline cannot certify.
Waiting event names are in PreparationTask.waiting_for; profile.received_events
provides synthetic observed state. Mark waiting before receipt; do not silently schedule
submission completion from estimated wait duration.
Shared task required before earliest supported deadline; all target-specific tasks distinct.
Conservative (hours_high) feasibility; lower-bound infeasibility only where proven.
No-fit heuristic -> at_risk, not categorical proof. Detect cycles/missing dependencies.
Retain completed IDs only if task still present and compatible.
Return target criteria/evidence, allocations and actionable next task.
Changed subset may reallocate shared capacity, but unrelated task content/completion
must be preserved; explain any capacity-caused rescheduling.

## API — Epic 1/3/4/5

GET /api/health; GET /api/opportunities; POST /api/discover {query}
POST /api/examples (cached public snapshots only)
POST /api/plan {selected_ids, profile}
GET /api/plan/latest; POST /api/plan/{id}/accept
POST /api/refresh {url}
POST /api/simulate {opportunity_id, fact_name, value} (separate synthetic copy/namespace)
POST /api/agent {message, selected_ids, profile}
GET /api/graph?ids=...
Mutations preserve original source facts. No API for internship applications or email.
One synthetic demo profile; concurrent plan acceptance checks current versions.
UI and API same origin; local bind 127.0.0.1.
Errors return safe summaries. Tokens stay server-side.

## Agent — Epic 5

Groq REST tool loop with <= 5 rounds and 4–6 typed tools. Tools read actual source/graph
or create proposed plans/revisions. The LLM never writes Cypher or selects a graph name.
Validate IDs and tool arguments. Record actual returned calls, result count and latency.
Structured results and evidence drive user decision; narrative must not introduce a
fact that the tool did not return. LLM may explain, not certify unknown eligibility.
429/timeouts explicit; deterministic review button remains available and labeled.

## Verification

tests/test_sources.py and test_planner.py cover semantic cases; graph tests run against
actual isolated test graph and bounded fixtures. Root proof script makes real TinyFish
and Groq calls without printing keys and verifies plan persistence and selective impact.
Full UI proof begins after the API slice. Record untested features accurately.

