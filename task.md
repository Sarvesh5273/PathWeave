# Task tracker

Updated: October 16, 2026, early morning IST.

## Current state

- Stage: local MVP built and verified. Work paused at Sarvesh's request to wrap up.
- Official deadline: October 18, 2026, 23:59 IST.
- Internal submission target: October 18, 2026, 20:00 IST (proposed buffer).
- Team: Just_Chill; user supplied a registered team panel with 1/4 seats filled.
- Registration/team state has not been independently checked in the signed-in panel.
- Implementation: saved local MVP. Git initialized; Python environment and pinned Docker image ready.
- Local FalkorDB is healthy and has executed a real Cypher smoke query. Persistence
  directory matches the volume; accepted plan, fact versions and completed work survived container restart.
- Product idea: internship discovery/preparation planner; original vision saved.
- Recommendation: keep domain, narrow to shared preparation and explained replanning.
- Product name: pending. Primary hackathon track recommendation: Agents That Act on Connected Data.
- Sarvesh accepted the narrowed direction and requested an independent review before implementation.
- Review verdict: revise, then conditional go. Scope now leads with real application
  blockers, typed compatibility and selective fact-change impact. Local implementation and verification are complete.
- All delegated work is completed. Agents remain listed for reuse; root integrated and reviewed their modules.
- Technical choices: Codex owns implementation decisions; Groq/free APIs preferred.
- Sarvesh says he is available enough; exact working hours remain unspecified.
- External submission: no submission action has been performed in this session.

## Next action

Resume only when Sarvesh asks. Read docs/next-session.md first.

Give Sarvesh a walkthrough of the working local app and graph decisions. Then resolve
hosting account/database endpoint, protect the public demo and deploy; prepare the
recorded video and exact submission package. No new broad research or provider switch
is needed. Groq Qwen passed after context reduction. TinyFish key is in execution
environment, not project .env; configure both provider keys on the deployment host.

## Flagged remaining work

- **Required delivery:** public repository, recorded demo video, complete final README/form
  and verified submission receipt. Nothing has been published or submitted.
- **Preferred delivery:** public deployment; hosting account and DB endpoint needed.
- **Quality before public use:** request limits, clear shared-demo boundaries or session
  isolation, and clean hosted setup verification. Current app is a synthetic local demo.
- **Participant contribution:** Sarvesh's technical walkthrough and verification remain pending.
- **Event uncertainty:** submission opening/edit policy, formal rubric/demo limit and blog method.
- **Compute:** deployment and video are the remaining substantial block. Estimate and flag
  the work before extensive new agent runs, broad research or rendering. Do not repeat
  successful tests unless a concrete change or failure requires it.
- **Running locally:** API at 127.0.0.1:18080 and persistent FalkorDB container remain
  available for inspection. All delegated agents are completed; no background task scheduled.

## Completed

- [x] **R01. Read the user-provided event material.**
  Owner: Codex. Evidence: attachment read; private copy in docs/private/.
- [x] **R02. Review the official overview, rules, schedule, resources, FAQ, article, conduct and terms.**
  Owner: Codex. Evidence: docs/hackathon-review.md; docs/research/sources.md.
- [x] **R03. Check organizer/sponsor, tracks, required technology and deliverables.**
  Owner: Codex. Evidence: review with primary source references.
- [x] **R04. Investigate judging and timeline gaps.**
  Owner: Codex. Evidence: unweighted organizer advice found; opening/track discrepancies recorded.
- [x] **R05. Research minimal FalkorDB architecture and sponsor examples.**
  Owner: Codex research agent. Evidence: technical-direction.md; research sources.
- [x] **R06. Review hackathon skills and create durable project documentation.**
  Owner: Codex. Evidence: README.md, AGENTS.md, tracker, review, strategy, decisions, build notes.
  Verification: all nine Markdown files are nonempty; local documentation links resolve;
  the supplied source is preserved under ignored private docs.

## Pending checks

- [ ] **R07. Resolve submission opening and submission edit policy.**
  Owner: Sarvesh + Codex. Acceptance: signed-in panel or organizer clarification,
  with timestamp and evidence. Public schedule says Oct 15, 00:01; pasted team panel
  says Oct 17, 01:03. Team changes are said to lock after submission.
- [ ] **R08. Confirm judging rubric, demo length, judging/results dates and blog entry method.**
  Owner: Codex; organizer clarification if needed. Acceptance: official answers or
  explicit “not published” notes. Do not delay the MVP while awaiting this.

## Product planning

- [x] **P01. Assess the proposed idea honestly.**
  Owner: Sarvesh supplies idea; Codex evaluates. Acceptance: clear keep/change/reject
  verdict, concrete failure risks, and one graph-dependent demo scenario.
  Evidence: docs/idea-assessment.md and scope.md; primary opportunity sources reviewed.
- [x] **P01b. Independent adversarial review.**
  Owner: fresh Codex reviewer. Evidence: docs/independent-review.md. Verdict: revise,
  then conditional go; stronger demo and behavior cases incorporated into scope.
- [x] **P02. Select primary track and freeze MVP scope.**
  Owner: Sarvesh + Codex. Acceptance: docs/hackathon-build/scope.md with user,
  workflow, graph role, demo, necessary features, cut features and assumptions.
  Narrow direction accepted by user. Updated scope and proof gate record review changes;
  final task-level freeze follows PRD/spec. Primary Track 01 remains recommended.
- [x] **P03. Write product acceptance criteria.**
  Owner: Codex. Acceptance: prd.md with outcomes and verifiable demo cases.
- [x] **P04. Write graph model, queries and implementation spec.**
  Owner: Codex. Acceptance: spec.md with schema, bounded tools, data provenance,
  chosen versions, provider settings and failure behavior.
- [x] **P05. Write sequenced build checklist.**
  Owner: Codex. Acceptance: checklist.md; each task has spec reference,
  concrete build work, acceptance criteria and a verification step.

## Implementation milestones (expand after scope)

- [x] **B01. Initialize Git and prove the riskiest graph query.**
  Acceptance: reproducible seeded FalkorDB query returns expected multi-hop evidence.
- [x] **B02. Deliver one complete task through the agent and interface.**
  Acceptance: real tool call, real FalkorDB result, visible evidence and persisted action.
- [x] **B03. Prove a relationship change changes the result.**
  Acceptance: expected before/after output; evidence identifies changed relationship.
- [x] **B04. Verify failure paths and persistence.**
  Acceptance: missing evidence is explicit; DB/LLM outage handled; memory survives
  restart if memory is a claimed capability. Only Track 01 is claimed; no application-level multi-agent handoff claim.
- [ ] **B05. Deploy or verify fresh local setup.**
  Acceptance: another clean environment can follow the documented commands.

## Verified build evidence

- 133 regression tests passed, including real disposable FalkorDB graphs.
- Actual backend TinyFish Search and Fetch passed; browser refresh checked official EPFL.
- Live Groq Qwen 3.8 27B tool loop passed in 1.69 seconds after repeated-context reduction.
- Browser verified plan, receipt, selective simulated repair, acceptance recovery.
- Database container restart preserved accepted state, completed CV and fact versions.
- Setup, dependency lock, graph model and demo walkthrough are written.
- Public deployment, video, hosted setup and Sarvesh's technical explanation remain pending.

## Submission milestones

- [ ] **S01. Freeze features by Oct 18, 14:00 IST (proposed).**
  Acceptance: only reproducibility, correctness and demo fixes remain.
- [ ] **S02. Complete public README and submission materials.**
  Acceptance: public repo, graph model, dependent Cypher/algorithms, setup,
  working demo video, deployment or local setup, tracks, explicit AI disclosure.
- [ ] **S03. Verify Sarvesh can explain the submission.**
  Acceptance: walk through schema, queries, architecture and decisions; record
  actual contribution/verification. AI-generated work alone is insufficient.
- [ ] **S04. Finalize human team before submission and review exact form.**
  Acceptance: team confirmed; all field values and links ready for final approval.
- [ ] **S05. Submit with user authorization and verify receipt.**
  Acceptance: official panel shows the submission with timestamp/ID; record evidence.
- [ ] **S06. Optional blog entry after the core submission is ready.**
  Acceptance: official method confirmed and working project explained honestly.

## Resume rules

Read docs before acting. Update checkboxes only with evidence. Add new tasks or changed
decisions without erasing the history. End each work session with the next action here.

