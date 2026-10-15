# Build Checklist

Build mode: autonomous, user explicitly requested implementation and independent agents.
Reviewer/integrator: root. Agents own separate modules from spec.md.
Verification: automated meaningful behavior checks plus integrated UI inspection.
User check-ins: progress updates; ask only for required inputs or concrete review.
Git: local milestones; publication and submission await the appropriate authorization.

- [x] **1. Runtime and shared contracts**
  Spec ref: spec.md > Architecture and ownership
  What to build: Python environment, pinned Docker/Compose, models/config and Git.
  Acceptance: database responds; credentials ignored; typed imports work.
  Verify: Docker health, Python imports, git check-ignore.

- [x] **2. Live source ingestion**
  Spec ref: spec.md > Source Layer
  What to build: TinyFish search/fetch, supported adapters and labeled snapshot examples.
  Acceptance: URL/fragments/cycle retained; unknowns stay unknown.
  Verify: source behavior tests and genuine backend provider call.

- [x] **3. Graph model and prerequisite tools**
  Spec ref: spec.md > Graph Store
  What to build: versioned facts, explicit recipes, prerequisite closure and evidence paths.
  Acceptance: shared base once; program-specific document/receipt rules distinct.
  Verify: actual FalkorDB integration tests.

- [x] **4. Deterministic preparation plan**
  Spec ref: spec.md > Planner
  What to build: eligibility states, precedence, waiting events and shared weekly capacity.
  Acceptance: exams protected; incomplete evidence never certifies readiness.
  Verify: planner cases including deadlines, unknowns and waiting dependencies.

- [x] **5. Selective change and acceptance**
  Spec ref: spec.md > Graph Store
  What to build: semantic diff, exact affected paths, immutable plan proposals and acceptance.
  Acceptance: no-op refresh unchanged; one fact affects relevant work; old plans retained.
  Verify: no-op/change/stale-accept/restart tests.

- [x] **6. Agent and API integration**
  Spec ref: spec.md > Agent / API
  What to build: real tool-calling loop and bounded routes.
  Acceptance: tool trace is real; proposed action uses graph results.
  Verify: provider call and integrated proof script.

- [x] **7. Product interface**
  Spec ref: spec.md > API
  What to build: discover/select/plan/review flow with next action, timeline and evidence.
  Acceptance: a user can complete the demo without reading source code.
  Verify: browser flow and responsive layout.

- [ ] **8. Reproducibility and proof report**
  Spec ref: spec.md > Verification
  What to build: README, seeded demo, dependency locks, setup and proof results.
  Acceptance: clean setup and restart recover accepted state.
  Verify: local proof cases pass; setup/docs written. Clean hosted setup still pending.

- [ ] **9. Submission preparation**
  Spec ref: prd.md > Submission Proof Points
  What to build: graph model/queries, video script, screenshots and accurate AI disclosure.
  Acceptance: reviewable package matches working behavior.
  Verify: local checklist and participant walkthrough.

- [ ] **10. Final submission**
  Spec ref: prd.md > Submission Proof Points
  What to build: review final team and exact official form; submit authorized package.
  Acceptance: official receipt recorded.
  Verify: user authorization and official submission readback.

