# Independent product reassessment — October 16, 2026

User request: reconsider continue versus pivot after comparing Just Chill with Scout.
Latest clarification: **Scout's actual discovery workflow, followed by preparation**.
This is not a request merely for a similar-looking search screen, nor an exact browser
bug reproduction. No wholesale rebuild or external delivery action occurred.
After the review, Sarvesh clarified that inspiration-led replication is acceptable.
The reuse warning concerns actual pre-event implementation, not inspiration itself.

## Verdict

[Likely] **Continue the internship domain; materially revise the product.** Retain
Just Chill's graph-backed fact/recipe/planning contracts and rebuild the weak discovery
layer to support the clarified flow. Do not ship unchanged, transplant Scout wholesale,
or switch to an unrelated domain simply to look more graph-oriented.

One independent read-only reviewer inspected both codebases. Root supplied a fresh
non-persisted search probe and independently checked the important extraction findings.
No winning odds, formal judging weights or full Scout feature-parity estimate were
established. The reviewer completed; no active agent task remains.

## Evidence from the independent source review

Scout paths below refer to commit `0fbad8cc71f92849e5a9a90ee2dc30e5496f12eb`, cloned
temporarily for review. Its code was not installed or executed.

| Code reference | Observed behavior |
| --- | --- |
| Just Chill `app/sources.py:800–827` | Actual TinyFish Search followed by bounded Fetch |
| Just Chill `app/sources.py:668–698` | Four specialized adapters; generic pages retain unknown facts |
| Just Chill `app/graph.py:352–438` | Prerequisite closure, shared tasks, evidence and fact versions from FalkorDB |
| Just Chill `app/recipes.py:49–154` | Typed facts activate authored preparation recipes; compatible base documents are shared |
| Scout `artifacts/api-server/src/pipeline/run.ts:147–355` | Preference-driven searches, board/posting collection, extraction, browser fallback, matching, ranking and storage |
| Scout `artifacts/api-server/src/pipeline/extract.ts:154–184` | General listing extraction; evidence can be paraphrased and month-only deadlines inferred to month end |
| Scout `artifacts/api-server/src/routes/listings.ts:23–99` | Listing filters, sorting and persistent save/hide actions |
| Scout `lib/db/src/schema/listings.ts:38–89` | PostgreSQL listing records and hunt scores/save flags; date-only deadlines and free-text eligibility |

[Certain] The fresh Amazon probe returned a real non-example listing but no known
structured planning facts. Its source contained useful degree, programming and CS
fundamental qualifications. Thus retrieval exists, while the general discovery-to-
preparation bridge does not yet work usefully. Exact user browser failure is unknown.
Full probe and source facts: research/scout-reassessment-evidence.md.

## Recommended boundary and product bar

**Preferences → live discovered shortlist → explicit selected targets → reviewed,
typed, source-supported requirements → FalkorDB preparation/replanning.**

The discovery portion should deliver the user's Scout-style behavior: role/location
and visa/funding preferences, search/read of actual postings, deduplication, ranked
results with reasons, source evidence, filters and saved/hidden targets. Coverage,
refresh/background behavior and browser fallback must be bounded explicitly rather
than silently called full parity. Browser automation requires applicable cost approval.

Selected listings must yield usable preparation, not merely unknown placeholder cards.
Keep preparation across targets under one budget, protect exams, preserve compatible
completed work, show the next useful action, and persist accepted state. New skill
requirements need typed facts and explicit recipes; they cannot be promised merely
because the finder extracted a free-text eligibility sentence.

Ranking scores are preference relevance, not selection probability or eligibility.
Salary/relocation does not certify all costs covered. Approximate deadlines must stay
approximate; do not copy Scout's month-end inference into certified scheduling.
Unknown fields stay unknown and source-derived requirements need attributable evidence.

## Integration alternatives

- **Revise current discovery — recommended:** preserves substantive graph/planner work
  and a cleaner event-work boundary; still substantial work, not a generic parser patch.
- **Port planner into Scout:** larger integration surface and schema translation;
  risks making FalkorDB an appended feature rather than the product's context layer.
- **Bridge Scout API:** potentially faster discovery but still needs requirement and
  provenance translation; adds availability/configuration dependencies. Reuse concerns
  are not erased by changing transport. No public API contract was verified here.
- **Unrelated pivot:** throws away verified original work without evidence of better
  contest prospects and compresses delivery/participant-understanding time.

## Graph proof and execution gate

[Likely] Strong demo: change one selected target's requirement in a labeled simulation;
show graph paths identifying only its dependent preparation; let the agent propose a
revision while unrelated targets and completed compatible work remain usable. Broad
search alone is not the graph differentiator. No official policy should be altered or
misrepresented for the demo.

Before implementation, write a revised acceptance checklist and a bounded estimate
for the clarified product. Validate two non-example official sources through discovery,
typed evidence, meaningful graph-derived preparation and selective repair. Preserve
existing state and protect repository/video/clean-setup/participant-explanation time.

The reviewer's earlier **6–10 focused hours** was explicitly a **thin-slice estimate**,
not an estimate for full Scout parity, deployment or final delivery. Its suggested
45–90-minute browser reproduction block is not warranted without exact failing steps;
the user clarified the desired product instead. Do not spend that block automatically.

If the integration gate fails, an honestly bounded preparation demonstrator with
allowed Docker/local setup is the fallback—not misleading claims of full discovery.

## Compliance and deployment

[Certain] Recorded Scout commit date is October 13, before the October 15 event start.
Rules permit general libraries/templates/infrastructure/public APIs, but no organizer
approval of wholesale existing-product reuse was obtained. Preserve provenance and
seek clarification for substantial incorporation; neither eligibility nor rejection
is established by this review. Organizer contact needs applicable authorization.
No organizer clarification is required merely to take inspiration from Scout's
workflow and author new event implementation; do not conflate that with source reuse.

[Certain] Docker, self-hosted FalkorDB and Cloud are accepted. Local-first was not a
rules error. Free Cloud docs lack TLS, persistence and backups. A persistent Docker
host with private database networking and HTTPS for the application is a possible
architecture, not a verified free hosting offer. No deployment happened.

AI disclosure and Sarvesh's own technical explanation/verification remain required.
His clarified product requirement is recorded; no unobserved testing is attributed to him.
