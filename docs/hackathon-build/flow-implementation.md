# Intended flow and first implementation slice

Updated October 17, 2026, IST. Sarvesh authorized starting implementation after
locking project-scenario exploration and three-component funding. D026 supersedes
the earlier discussion-only pause for this slice.

## Intended full flow

Project scenarios -> tentative explained interests -> edit/retest -> visible search
preferences -> source-supported strict matches -> explicit target selection ->
editable availability/timetable and readiness baseline -> shared learning roadmap ->
progress tracking and replanning after source or calendar changes.

Interest is different from demonstrated knowledge. Requirements and selection stages
need attributable evidence. Resources/prerequisites and availability must drive a
real learning plan rather than only a collection of short practice tasks.

## Implemented in v0.5.0

- 12 authored illustrative company/research project scenarios, two per direction.
  Students rate interest, mark unfamiliar/uncertain, skip and revisit questions.
- Up to three tentative suggestions explain the chosen activities, disclose partial
  answers/ties and offer small activities to try. Editable roles and keywords feed
  search without starting provider requests automatically. Retesting clears responses.
  Responses stay in browser storage; no aptitude or validated career prediction claim.
- Fine-tuning and shortlist filters are visible sections rather than collapsed details.
- Backend applies selected location and funding cumulatively. Stipend/living support,
  accommodation AND round-trip travel need attributable source excerpts. Unsupported,
  conditional or conflicting coverage stays unconfirmed. Explicit mismatch is excluded.
  The optional unconfirmed view is separate from matches; saved/hidden records retain
  their displayed constraint status. No silent relaxation of the hunt's requirements.
- Source reads support filter metadata before target selection without LLM calls.
  Generic qualification extraction remains after selection. Old hunts are evaluated
  using their actual stored snapshots; missing/stale snapshots cannot pass strict filters.
- Search ceilings now 12 queries/run and 25/minute; Fetch uses up to 10 URLs/request
  and a 45-URL run ceiling, with the existing 900/day ledger. Reads request a one-hour
  TinyFish cache tolerance. These are ceilings, not guarantees of complete coverage.
- Rule-based company/ATS/web/research query planning, posting/feed parsing and the
  existing named-company browser fallback remain. Existing source time and evidence
  limitations remain explicit. SDK v0.8/Replit model/Postgres were not adopted.

## Verified

88 affected offline/API tests passed in 0.73 seconds, including disposable real
FalkorDB graphs. Cases cover all three components, location mismatch, missing/negative/
conditional coverage, cost-to-user exceptions, stale and unrelated snapshots, cohort
boundaries and cumulative API filtering. Syntax checks passed.

Actual main-app browser check, using previously retrieved sources and no new provider
requests: all 12 questions -> explained software/data suggestions from test answers ->
user-editable added role/keywords -> return to saved suggestions -> retest reset.
Visible fine-tuning confirmed. Saved Japan hunt had three source-supported location
results with unrestricted funding; adding the three-component funding filter yielded
zero confirmed matches. Unconfirmed records stayed available in the review view.
These test responses are not Sarvesh's interests, personal assessment or verification.
The old main plan/hunt data was preserved. No paid Agent, new agent run or publication.

## Next slice and unresolved limits

- Editable weekly timetable and semester-calendar upload/review, exam buffers and
  exact study slots are not implemented. Current weekly-hours planner is an estimate.
- Baseline/topic-check policy and beginner start-from-basics path still need agreement.
- A topic/prerequisite/resource curriculum and general sourced interview-stage mapping
  are not implemented. Existing bounded recipes do not fulfill the full learning roadmap.
- Funding checks recognize explicit bounded wording; omitted/unclear wording remains
  unknown. They do not prove sufficient living allowance, zero expense, eligibility or
  a universally complete discovery result. Cost exceptions need source review.
- Structured extraction/ranking, 36-page extraction allowance, $1/day AI costs and
  Replit service are Scout reference behavior, not the current default implementation.
  Groq selected-target reliability and broader source coverage remain flags.
- Browser Agent retains the prior authorized total-budget reservation. No new $1.50/day
  operating allowance or recurring provider work is inferred. Auto-refresh stays disabled.
- Hosting, public repository, recorded video, participant explanation and submission
  receipt remain unfinished. Public-use controls and event personal-data restrictions
  still require attention. No submission-ready or winning-outcome claim.

Continue from this slice, not an old Scout rewrite or repeated full context audit.
