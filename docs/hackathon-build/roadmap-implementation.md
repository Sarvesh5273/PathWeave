# Roadmap and timetable checkpoint — October 18, 2026, IST

## Implemented locally in v0.7.0

- Selected source skill facts map to reviewed `Topic` nodes in FalkorDB. Topic
  prerequisites use `PREREQUISITE_OF`; authored resources use `COVERS`; source
  facts use `MAPS_TO`. Identical topics are shared across selected targets.
- The roadmap traverses the topic prerequisite closure and presents it in learning
  order. Resources are an authored starter catalog with explicit URLs; they are
  guidance, not internship-source claims or a universal syllabus.
- Required-topic checks are editable self-ratings: comfortable, needs review, new
  to me, or unsure. They change the suggested start point only. They do not alter
  sourced requirements, remove required preparation, or claim assessed knowledge.
- The timetable accepts optional hours for each weekday. Once a per-day pattern is
  set, blank days are unavailable. Multiple exam weeks and individual holidays can
  be added/removed. The deterministic planner protects those dates and schedules
  the shared target workload against the resulting capacity.
- Saved opportunity facts receive an idempotent local topic-graph backfill at app
  startup. This makes no Search, Fetch, Groq or TinyFish Agent call and does not
  rewrite saved plans or source facts.

## Verification and limits

- Full local gate: **819 passed** in 4.03 seconds, including disposable real
  FalkorDB cases. One existing Starlette/httpx deprecation warning remains.
- Focused browser fixture passed daily hours, multiple exam/holiday blocks,
  roadmap rendering, source-linked resources and rating-triggered replanning.
- Port 18080 reports v0.7.0 with FalkorDB healthy and Groq/TinyFish configured.
- No provider call, paid Agent run, deployment, publication or submission occurred.
- A roadmap appears only for reviewed topics supported by extracted skill facts.
  Unknown/unreviewed topics remain verification tasks; no generic syllabus is
  silently invented. Older saved plans remain unchanged until the user builds a
  new proposal. No quiz validates competence.
- Calendar-file/ICS import, exact clock-time study sessions, automatic course
  ingestion and broadly sourced interview-stage curricula are not implemented.
  The implemented timetable is editable per-day capacity plus semester blackouts.

## Delivery state

Public repository, demo video, final submission materials and official receipt are
still pending. Preserve saved hunts/plans and Groq configuration. Delivery actions
retain their authorization gates.
