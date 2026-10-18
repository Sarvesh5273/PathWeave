# Scout engine parity — implementation amendment

Updated October 16, 2026, IST. User requested inspiration-led replication of Scout's
actual engine, preserving its considered behavior and TinyFish Agent/other features.
Flag gaps separately; do not silently replace the engine with a simpler single-query
search. Original Scout source remains unmodified.

Reference: https://github.com/Sarvesh5273/Scout, reviewed commit
`0fbad8cc71f92849e5a9a90ee2dc30e5496f12eb` (October 13, pre-event).
The reference is design/provenance evidence, not a claim that this upgrade is finished
or that the original Scout pipeline was executed in this workspace.

## Current integration status (supersedes initial status cells below)

Current direction supersedes full-parity work: user said "forget Scout ... basic filter".
Default BasicDiscoveryEngine now retrieves cards and applies direct relevance rules
without LLM calls. Requirements/visa/funding enrichment is deferred until selection;
unknowns do not erase listings. Fresh Japan browser proof passed18leads58.88s with
two sourced Japan labels,0AI/Agent; save/reload passed. Last full gate752tests passed.
The AI-first Scout replica is retained in engine.py, not represented as the new default.
Reliable selected-target enrichment/full parity/hosting still unfinished. HENNGE detail
extraction rejected incomplete output and stayed unknown. See D023/task.md for current work.

Latest user failure supersedes readiness: actual Japan software/robotics hunts returned
zero/one listing, feed errors and Groq429 followed by stopped extraction. Scout parity
repair is active; do not substitute a partial/cached Amazon proof for the user's flow.
The missing .env TinyFish entry is fixed using the existing key, with file-only loading
verified. Actual default-capped Agent proof completed against Notion (3 links); old
"Agent not live verified" notes below are historical. Full search/collection/AI pacing
repairs and a fresh browser-initiated hunt gate remain unfinished at this point.

Confirmed repair evidence, not a readiness claim:

- Actual failed Workable feed publishes links as `/j/<shortcode>` without an
  organization segment. The earlier collector manufactured invalid URLs, causing
  page-not-found errors. The source agent is fixing that real feed shape, escaped
  JSON parsing and description reuse rather than filtering the failures away.
- Groq pacing now uses shared per-model TPM admission, actual token usage and safe
  reset headers. One bounded wait/re-attempt replaces immediate 429→permanent stop;
  exact evidence validation and explicit incomplete extraction remain. Standalone
  fresh Amazon extraction passed with the compact request, not full-hunt acceptance.
- Application key/rate linkage is now checked directly using the read-only Wallet API.
  A default150-step Agent run at USD0.016/step fits USD2.40 maximum. A real Notion proof
  completed with three internship links and reported3steps. Observed wallet decrease
  was0.048USD, not automatically isolated billing proof. Full2.40 reservation is retained
  conservatively under the existing3USDtotal; no second paid run or top-up occurred.
- Scout's new/saved/hidden, sort, text/visa/funding/fit listing views, summary and
  source endpoints are now authored/tested against recorded behavior; UI exposes
  these filters without changing the cream design. This does not prove live discovery.

Sarvesh requested parallel implementation. Four agents authored source/ATS collection,
general Groq extraction/ranking, TinyFish transport/browser and the preparation bridge.
Root authored engine.py, state.py, hunts/jobs/selection routes and Scout-style UI plus
optional activity exploration. Independent review defects were corrected. Last full
regression gate: 586 passed; later worker-path case passed separately. Real bounded
engine→graph proof and actual browser/API/FalkorDB acceptance/reload passed. **Full
parity/broad coverage/live Agent remain unproved**, as detailed below.

- Source/ATS parsing, transport, extraction/ranking and bridge are implemented with
  offline tests; the bridge includes real disposable graph tests.
- Durable browser-scoped hunts, save/hide, run traces, queued execution and manual
  reruns are authored. SQLite requires persistent local disk and is not a distributed
  multi-host store. Preparation remains one shared synthetic FalkorDB workspace.
- General selected listings now reach source-bound skill preparation; root API/graph
  tests verify useful tasks/evidence and unknown requirements remain blockers.
- Optional exploration, preferences, ranked cards, selection, save and hunt reload
  pass desktop/390px browser checks with mocked discovery responses. This is not live
  provider/UI end-to-end proof.
- A real Amazon Fetch→Groq extraction produced exact qualifications, not all unknowns.
  The bounded real pipeline proof passed: 11.42s, 3 searches/8 fetch URLs/2 extraction
  attempts, German Amazon target with 9 known facts/21 tasks/82 paths. Groq quota/source
  failures made it explicitly partial, with deterministic match fallback. Main local
  v0.2.0 app was restarted at port 18080 with saved main state retained.
- Scheduler capability is authored for active user hunts (24-hour cadence, three-day
  activity window, two-hour failure retry) but disabled by default. No recurring work
  was authorized or started. Public auto-refresh showcase hunts and reviewer reserve
  features remain unfinished; do not silently call them complete.
- Agent fallback/cache/recovery/step-limit transport is authored and mocked. User
  authorized $3 total existing-credit proof, but account custom max_steps is beta-gated
  and not verified. Live Agent remains disabled; no money was spent or added.
- Current TinyFish pricing was fetched: $0.016/Agent step; Search/Fetch free with stated
  limits. Duration alone is not a hard cap. A supported transmitted max_steps must
  precede metered proof; do not set a verification flag without account evidence.

Current proof/scripts: tests/test_discovery_*.py, scripts/check_discovery_ui.py
(mocked UI), scripts/proof_scout_engine.py (real bounded pipeline, no Agent, disposable
graph). Source shapes, exact run limits and provider failures must remain visible.

## Engine stages to preserve (initial plan; current status above)

| Stage | Scout reference | New implementation status / acceptance |
| --- | --- | --- |
| Preference surface | `lib/db/src/schema/hunts.ts:4–16` | First contract implemented in `app/discovery/contracts.py`: roles, keywords/exclusions, places, remote, seniority, opportunity types, visa, citizenship, funding, companies. Not connected to UI/API yet. |
| Prioritized multi-query planning | `pipeline/plan.ts` | Implemented in `app/discovery/search_plan.py`; company-first, ATS/web/program searches, secondary keywords/citizenship/places, deduplication. No network call here. |
| Source classification and URL identity | `pipeline/discover.ts`, `pipeline/urls.ts` | Pending: distinguish boards, postings and pages; preserve source attribution, canonical identity and exclusions; keep current public-URL safety checks. |
| ATS feeds and posting leads | `pipeline/feeds.ts`, `pipeline/collect.ts` | Pending: Greenhouse, Lever, SmartRecruiters and Workable feeds; Workday posting links; follow individual posting links, not only extracted page text. |
| Multi-wave Search/Fetch | `pipeline/run.ts:151–242` | Pending: batched reads, multiple collection waves, per-source failure, retained links and source traces. Old endpoint still runs its bounded original implementation. |
| General structured extraction | `pipeline/extract.ts` | Pending: arbitrary actual postings/programs, index-page leads and closed pages; all discovery fields and source evidence. Adapt AI provider without losing the stage. |
| Automatic TinyFish Agent fallback | `pipeline/agent.ts`, `pipeline/run.ts:244–320` | Pending: named-company portals unreadable by Fetch, seniority-aware goal, Ashby internship filtering, validated opening links, 24-hour goal/preference-keyed cache, follow-up reads. Preserve automatic selection once metered use is configured/authorized; no per-call confirmation barrier. |
| Freshness and deduplication | `pipeline/run.ts:322–330`, `pipeline/store.ts` | Pending: recheck old/unseen postings, distinguish closed/unknown/stale, deduplicate candidates, retain new-since-last-run behavior. |
| Matching and deterministic ranking | `pipeline/match.ts`, `pipeline/relevance.ts`, `pipeline/places.ts` | Pending: AI role/location/eligibility-fit verdicts with heuristic fallback; original role/level/location/visa/funding/keyword scoring, caps and reasons; country/city and remote handling. Match is not eligibility certification. |
| Hunts and listing actions | `routes/listings.ts`, `schema/hunts.ts`, `schema/listings.ts` | Pending: separate query/hunt results from explicitly selected targets; sort/filter/save/hide actions; private synthetic demo boundaries versus public showcases. |
| Queue, budgets, usage and traces | `pipeline/queue.ts`, `pipeline/context.ts`, `pipeline/recorder.ts`, `lib/config.ts` | Only typed per-run ceilings implemented. Execution, atomic/shared reservations, one-active-run-per-hunt, queue limits, durable traces and provider accounting remain pending. |
| Refresh scheduler and caches | `lib/config.ts:67–74`, scheduler/cache modules | Pending: preserve showcase/user cadence, active-user window and failure retry behavior as a capability. Do not start unattended provider-consuming jobs without applicable authorization. |
| Selected listing → preparation | Just Chill graph/model/recipe contracts | Pending general bridge: reviewed typed requirements and skill/document recipes, one capacity/exam calendar, graph evidence and selective repair. No raw match score or free-text label becomes a certified requirement. |
| Optional interest explorer | Original user vision, D017/D018 | User accepted lightweight optional exploration; build after the discovery-to-preparation core. Editable starting preferences; no aptitude/career/selection score. |

## Per-run baseline (recorded Scout config, not current provider contract)

Preserve baseline ceilings: 12 searches, 45 fetch URLs, 2 Agent runs, 36 extractions,
8 boards, 5 postings per board, 10 leads, 6 rechecks; 120-second Agent duration,
150-second soft and 270-second hard run deadlines. New `RunBudget` records them;
it does not yet enforce orchestration or authorize spending. Cross-field validation
rejects a soft deadline later than the hard deadline.

Scout also has daily AI/Agent budgets, reserved reviewer capacity, client/global
request controls, queue/concurrency limits and caches. Preserve their purposes and
expose differences when adapting to Groq or a deployment topology. Do not treat
October 7 price/quota comments in Scout as verified current provider limits.

## Gaps flagged separately from parity

1. **Approximate deadlines:** Scout's extraction prompt converts month/year into the
   month's last day (`pipeline/extract.ts:161`). Preserve the original wording and
   precision; do not certify that inferred date as an official deadline in preparation.
2. **Funding classification:** its "fully funded" rule is salary/stipend plus travel
   **or** housing (`extract.ts:179`). Keep component evidence visible and flag fees,
   uncovered costs and uncertainty; do not promise zero out-of-pocket expense.
3. **Evidence strength:** visa/funding notes allow close paraphrases (`extract.ts:160`).
   Preparation requirements need attributable source excerpts and versions rather
   than silently upgrading a model summary into verified facts.
4. **Provider dependency:** Scout uses Replit AI Integrations and `gpt-5.6-luna`, billed
   to Replit credits (`replit.md:14–20`). Groq remains preferred here. A provider adapter
   must support validated structured outputs, quotas and visible failures; identical
   model outputs or ranking accuracy cannot be promised without comparative testing.
5. **Metered Agent:** capability preservation is not permission to spend. Configure
   an authorized budget once, then preserve automatic fallback within it. No paid
   Agent call was made here. A duration cap alone is not a proven hard step/spend cap;
   verify account-supported limits before claiming a strict dollar ceiling.
6. **Process-local coordination:** Scout's SDK semaphore and current graph locks are
   process-local. Shared budget/run reservations and graph updates need a deliberate
   single-process or cross-instance coordination strategy before hosted concurrency
   claims. No fix or hosted proof has happened yet.
7. **Rule boundaries:** Scout is pre-event work. Reimplement the behavior and keep
   provenance; do not present the existing source as newly authored event work.
   Personal/private graph ingestion is still outside this hackathon demo.

Input normalization, list/text safeguards, forbidden unknown preference fields and
timezone-aware query clocks are new contract choices; the reviewed query planner
matches Scout behavior, but exact generated Scout input-validation parity is not
claimed. Query-year hints never create actual cohort/deadline facts.

## Execution order and verification gates

1. **Completed slice:** preference contract, per-run ceilings and query planner.
   Twenty-five offline tests passed. Independent review found no query-planning parity
   blocker; its budget-order safeguard was fixed and covered. The reviewer did not
   rerun tests. No existing application endpoint, accepted state or provider was changed.
2. **Next slice:** source/ATS identity, feeds/link collection, validated extraction
   contract and budget-aware provider adapters. Read current TinyFish API docs before
   writing the Agent transport. Use mocked failure cases before any metered proof.
3. **Engine slice:** multi-wave orchestration, automatic fallback/cache, matching,
   ranking, fresh rechecks, traces, state/queue and controls. Account for skipped stages
   visibly; do not report a partial run as full parity.
4. **Product slice:** wire preferences/hunts and selected targets into general
   graph-derived preparation, then optional exploration. Preserve known graph behavior.
5. **Proof/delivery:** non-example official company and research sources through the
   whole flow; provider/cost limits, source failures and graph repair; UI testing, clean
   setup, video, public repo and Sarvesh's own explanation. External actions retain
   their separate authorization gates.

This is a substantial backend revision. No reliable full-parity estimate is available
yet; the earlier 6–10-hour estimate covered a thin end-to-end slice, not this complete
engine/UI/hosting/delivery scope. Time-box subsequent slices, report scope/cost blockers,
and protect delivery time before the October 18, 23:59 IST deadline.
