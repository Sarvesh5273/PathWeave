# Product Requirements

Status: implementation authorized October 15, 2026.
Primary track: Agents That Act on Connected Data.

## Product Summary

Students select sourced internship targets and receive one preparation plan. The agent
identifies incompatible requirements and external blockers, and revises the affected
work after a fact change. Research and Company share the same time budget.

## Epic 1 — Discover and select

- Live application-side TinyFish search/fetch reads public sources.
- Opportunity cards include source, checked time, cohort, category, call state,
  deadlines, benefits/fees and explicit unknowns.
- Up to three selected targets; source links alone do not mean eligibility.
- Supported source adapters cover EPFL, OIST and one public company listing; generic
  results keep unverified fields unknown. Do not claim exhaustive discovery.
- Calls closed at the source are not scheduled as current applications; future
  preparation is separate. A future deadline does not prove an open portal.

## Epic 2 — Requirements and compatible work

- Every assessed condition keeps its source fragment. Minimum conditions are separate
  from preferences. Unknown profile inputs yield needs-review.
- Shared CV/base preparation can be reused by explicit recipe; each program's final
  statement, document format and delivery channel remains specific.
- OIST recommendation requested is not recommendation received. External waiting
  cannot be represented as student effort. EPFL does not acquire a reference task.
- Synthetic profile only; no CV/passport/grade documents are uploaded.

## Epic 3 — One bounded plan

- One weekly budget across Research/Company/Shared work; exam weeks receive zero work.
- Dependency order is respected. Effort ranges are estimates.
- Show feasible under known estimates, at-risk, infeasible under proven bounds, or
  cannot-certify for missing facts/deadlines/external receipt.
- No claims of optimality or selection probability.
- Show one next useful action, persistent target selection and task completion.

## Epic 4 — Explained repair

- Semantic fact changes produce graph-derived affected targets/tasks and evidence paths.
- An unchanged requirement with changed page boilerplate does not stale plans.
- Changed OIST-specific fact leaves unrelated EPFL tasks and compatible completed
  base work intact.
- Source failure does not silently erase previous evidence or keep certifying it.
- Simulated policy updates are clearly labeled and cannot overwrite official facts.
- User reviews and accepts a proposed plan version. Stale proposals cannot be accepted.

## Epic 5 — Real agent and evidence

- Groq chooses typed tools; graph and deterministic code compute results.
- Trace includes actual tool, arguments, result and execution mode.
- Provider outages are explicit; deterministic fallback is labeled.
- An evidence panel exposes paths and fragments supporting the decision.
- Accepted plan survives API and database restarts.

## Submission Proof Points

A judge can reproduce live discovery, wrong-reuse prevention, recommendation waiting,
exam capacity, selective change impact and accepted plan recovery.
Public README records graph model, queries, setup, AI use and measured test results.

