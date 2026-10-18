# Task tracker

Current handoff: docs/project-handoff.md consolidates the intended product, delivered
v0.7core, latest five-step UI, actual verification scope and remaining work. README
now has “Planned development” separating unfinished features from delivery obligations.
All source/UI commits through2daa34bwere pushed to origin/main in this chat; subsequent
documentation updates need pushing. Repository visibility/video/submission receipt
are not established by that Git push. Current desktop frame is1120pxconsistently,
with880pxdetailed forms; prior whole-page880pxentries below are historical.

Latest screenshot correction: starburst branding removed; compact880pxdecision
screens and1120pxworking views, stacked mobile cards and balanced spacing authored.
No browser run. User visual review remains the next check; D033.

Latest UX revision: user requested screenshot-based redesign, cream/orange retained,
no browser runs. Five-step Direction/Search/Targets/Time/Roadmap flow implemented;
back/edit/saved entries and evidence view retained. JS syntax/HTML/control-reference
checks passed; browser/visual interaction validation not performed by request.
Next user hard-refreshes and reviews; preserve delivery focus and no provider reruns.

Latest UI pass: short entrance/navigation/hover/press/progress animations implemented
with CSS and browser APIs, reduced-motion respected. Local navigation/style check
passed without JS errors; no provider calls. No shadcn/React dependency migration.

Latest delivery step: product name PathWeave and tagline accepted; Just_Chill is the
team. User will publish manually using VS Code's configured GitHub account. Local
branding/README/graph model updated. Public repository URL/visibility not yet verified.

## Current checkpoint — October18,2026,IST (supersedes historical entries below)

v0.7.0 roadmap/timetable slice completed ~18:55 IST. Selected source facts map to
shared FalkorDB Topic nodes with prerequisite/resource edges; self-ratings set the
suggested start without certifying knowledge or changing requirements. UI supports
per-day hours, multiple exam weeks and holidays.819full local tests + focused offline
browser QA passed. Port18080runs v0.7, graph healthy, Groq/TinyFish configured. Saved
hunts/plans preserved; no provider/paid Agent call. See D029 and roadmap-implementation.md.
Public repo/video/form/submission/receipt are now the critical unfinished work and
require applicable authorization. Calendar import/exact clock slots/quizzes remain cuts.

v0.6.0progressive discovery is authored: early candidates, bounded Groq extraction/
preference scoring, cached Agent-link Fetch follow-through and sourced requirements
before selection.243affected tests passed with real FalkorDB/API checks. Final saved
source proof:27known facts/5tasks/67paths, plan readback, cannot_certify. Partial
extraction remains. Groq stays; Gemini untouched. No new paid Agent/public delivery.
See docs/hackathon-build/discovery-repair.md.

Port18080restarted with v0.6.0; one focused UI review remains. Sarvesh flagged
excessive time/compute; root acknowledged overbroad scope and
repeated live checking. Do not redo provider hunts/audits. Timetable/topic-check/full
learning-roadmap and delivery obligations remain unfinished.

Resume Oct18 ~18:30 IST: Docker and API were found fully stopped. Restored Docker,
FalkorDB and API18080 (v0.6.0, health ok, Groq+TinyFish configured). Saved state intact:
13 plans,5 hunts/runs; latest plans proposed. Walkthrough given; roadmap-slice design
under discussion before implementation. Timeline: internal20:00buffer close; delivery
package still untouched. No paid Agent/provider call in this restore.

Updated: October 17, 2026, IST — locked exploration/discovery slice implemented; v0.5.0.

## Current state

- Latest clarification (D027): user expects Scout's Search/Fetch/Agent plus page
  extraction and scoring with Groq as the LLM. Current default bypasses discovery AI
  extraction/scoring and lacks complete Agent-link readback. Discovery reliability is
  the recommended priority before timetable/resource-roadmap work. Match-score design
  remains discussion; locked strict location/funding gates remain. No code changed.

- Latest: Sarvesh authorized implementing the locked first slice.12project scenarios,
  explained editable suggestions/retest, visible settings and cumulative source-supported
  location/three-component funding filters are implemented.88affected cases passed;
  actual browser questionnaire/edit/retest/strict-view checks passed using stored sources
  without new provider calls. Main18080runs v0.5.0; previous plans/hunts preserved.
  Timetable/readiness/shared-learning roadmap remain pending. See D026 and
  docs/hackathon-build/flow-implementation.md; this supersedes the pause below.
- Latest product decision: Sarvesh says the app does not yet match his vision. Project
  scenarios for company/research interests and strict three-component funding are
  locked in docs/hackathon-build/interest-and-funding.md (D025). They are not implemented.
  Implementation is paused pending timetable/readiness/learning-roadmap discussion.
- Latest: user requested actual working flow without demo controls. Editable unknown-first
  background inputs, browser-scoped plans and self-reported progress/receipt are implemented.
  Cached examples and policy simulation are absent from the main UI and disabled by default.
  Old demo graphs/plans remain intact. 131 targeted preparation/API/graph tests and135
  extraction/quota tests passed. Fresh HENNGE compact extraction produced12supported
  facts,9tasks,14source-excerpt paths and real isolated accepted-plan readback in2.84s.
  Readiness remains cannot-certify for partial coverage; no complete-source claim.
  This supersedes prior synthetic-only/shared-preparation/HENNGE-empty claims below.

- Stage: historical local MVP verification complete; user now reports an unsatisfactory
  finder/preparation experience and requests a continue-or-pivot review against Scout.
  Sarvesh accepted Scout discovery plus preparation and requested full engine behavior
  including Agent. Four agents delivered source/ATS, AI extraction/ranking, browser
  transport and preparation bridge modules. Root added engine/hunts/queue/state/UI
  plus optional exploration. Independent integration defects were fixed. Last full
  regression run: 586 passed; additional worker test passed separately. Bounded real
  engine proof and actual browser/API/graph plan-accept-reload proof passed. Broad
  coverage/full Scout parity and public delivery remain unfinished. New default is
  source-first discovery with no LLM calls; selected-target extraction is separate.
  Fresh browser Japan hunt passed (18 leads, two sourced Japan locations, save/reload);
  review edge cases corrected. Latest regression gate: 752 passed. Selected HENNGE
  enrichment hit output truncation; target stayed visible/unknown (not a complete planner claim).
  User authorized $3 total Agent proof from existing credits, no purchase; live use
  has one actual Notion Agent proof (3 links); verified default150steps at0.016USD/step,
  conservative2.40USD reservation retained. No second metered run or top-up.
- Official deadline: October 18, 2026, 23:59 IST.
- Internal submission target: October 18, 2026, 20:00 IST (proposed buffer).
- Team: Just_Chill; user supplied a registered team panel with 1/4 seats filled.
- Registration/team state has not been independently checked in the signed-in panel.
- Implementation: saved local MVP. Git initialized; Python environment and pinned Docker image ready.
- Local FalkorDB is healthy and has executed a real Cypher smoke query. Persistence
  directory matches the volume; accepted plan, fact versions and completed work survived container restart.
- Product idea: internship discovery/preparation planner; original vision saved.
- Accepted revision: preserve Scout's discovery engine behavior, then shared preparation
  and explained replanning. Optional interest exploration follows the core build.
- Product name: pending. Primary hackathon track recommendation: Agents That Act on Connected Data.
- Sarvesh accepted the narrowed direction and requested an independent review before implementation.
- Earlier review verdict: revise, then conditional go. Baseline graph/blocker/repair
  implementation and verification are complete; Scout parity revision is not complete.
- All delegated work is completed. Agents remain listed for reuse; root integrated and reviewed their modules.
- Technical choices: Codex owns implementation decisions; Groq/free APIs preferred.
- Sarvesh says he is available enough; exact working hours remain unspecified.
- External submission: no submission action has been performed in this session.

## Next action

Latest priority: delivery triage. The intended local product loop now reaches v0.7;
do not reopen broad discovery/provider work. Have Sarvesh hard-refresh and review the
new timetable/roadmap once, recording only his actual feedback and understanding.

Current next action: with explicit authorization, prepare the public repository/README,
recorded demo and exact WeMakeDevs form package, then obtain separate final submission
authorization and verify the official receipt. Preserve saved state and provider config.
No paid Agent run, broad audit, deployment, publication or submission is implied.

Latest October 17: use the v0.4.0 normal flow to search live, select actual targets,
enter background/time, build a sourced plan and mark actual progress. Record user
feedback; do not call Codex's UI checks Sarvesh's understanding or verification.
Broad enrichment and public delivery remain flags. Hackathon recording should still
use synthetic inputs under the unresolved data rule. No new paid Agent calls/agents.

Final resume evidence: actual HENNGE/Japan browser hunt returned8leads with source
gaps. Selection built4verification/blocker tasks, versus9in the isolated fresh proof;
extraction reliability is still partial. Blank profile fields preserved; source
coverage guard prevents certification. Plan/hunt restored after restart. Final70
affected tests passed; no full-suite rerun claimed. Main18080running, temporary18081
server stopped. No fabricated user completion/receipt or technical understanding.

Latest user steer: "forget Scout ... basic filter". Prioritize reliable source listings
and direct role/location filtering, without requiring AI extraction before cards exist.
Root authored BasicDiscoveryEngine as the default API engine; old AI-first engine is
retained, not deleted. Detailed source-backed extraction runs on selected targets only.
Progress publishes retrieved leads without replacing earlier completed hunt history.
Latest fresh browser Japan gate passed in58.88s without AI or Agent; 18 leads include
ASM Japan and HENNGE Tokyo/Japan, not 18 certified Japan opportunities. Unknown places
stay unknown. Save/reload passed. Independent review fixes passed (index/stale evidence/
cohort/feed binding/place semantics). Latest full regression gate752passed. Selected
target enrichment remains limited; HENNGE attempt rejected incomplete output, preserved
target with unknown facts. Main restarted with v0.3.0 and .env-only TinyFish loading;
port-18081 verifier stopped. User tests basic finder next.
Keep cream UI and main saved plan; no more broad research/full parity rewrites.

Priority supersedes earlier UI checks: repair discovery against Scout's actual engine.
Sarvesh's saved Japan software/robotics hunts returned zero/one listings with feed
parse failures and Groq 429 followed by skipped extraction. These are real user-run
failures; do not call discovery ready from cached/partial Amazon or mock UI proof.
Existing inherited TinyFish key was saved safely to ignored .env and load verified
without inheritance; no credential printed. Two bounded agents repair AI admission/
token throughput and collection/feed parity. Root owns setup, worker/API status,
safe Agent verification and fresh browser-started hunt acceptance gates.
The first new browser-started Japan gate still failed: zero candidates after ~275s.
Full regression tests (690 at that point) did not establish useful live discovery.
Captured source/output diagnosis found separate output-token quota pressure despite
available combined TPM, plus typographic title normalization. Root added compact
line-ID evidence resolving to exact quotes and locality-first source ordering; AI
owner is adding separate output admission/nonreasoning mode. Do not repeat the full
hunt until these concrete fixes are integrated/tested. Proof script import was fixed;
the failed run data was recovered without starting another network hunt.
Keep cream UI and main saved plan; no unrelated rebuild or repeated brief questions.
Actual TinyFish BrowserFallback proof now passed against Notion with the application's
key: 3 internship page links, completed run, reported 3 steps. Default150-step limit
and application-account rate0.016 were verified first; full2.40USD reserved from the
existing3USDtotal ceiling. No purchase/retry. Configured default-cap Agent mode in
ignored.env; fresh app process needed after agent fixes. Do not claim the entire
Scout discovery flow works just from this standalone browser proof.

Have Sarvesh hard-refresh the main app and review the cream-grid interface described in
docs/hackathon-build/ui-direction.md. Targeted mock UI and actual isolated API/FalkorDB
checks passed, including selection→time setup→plan→accept/reload, task category views,
and mobile evidence. No new provider calls; no main plan/state changes. Backend remains
unchanged. Port-18081 verification server stopped; main 18080 remains running.
Record actual user feedback/understanding and preserve the remaining gates below.

Have Sarvesh try the updated app at http://127.0.0.1:18080 and record his actual feedback
and verification, not assumed understanding. Core flow is proven locally; source/AI
gaps remain explicit. Next remaining capability gate is reliable Agent spend/account
verification, followed by source/quotas robustness and showcase/reviewer reserve parity.
No paid Agent call occurred. Read docs/hackathon-build/scout-parity.md and delivery flags
before hosting; SQLite/queue changes mean earlier Vercel discussion is not a current
deployment recommendation. Preserve saved main plans; main reload showed its latest
proposal and one completed task, not an invented new acceptance.
Preserve new-code/pre-event provenance. Flag substantial remaining scope/cost and do
not treat the 6–10-hour thin-slice estimate as full engine/UI/delivery parity. Paid Agent
runs, recurring provider work, deployment, publication and submission require applicable
authorization. All agent tasks are completed. Main API is running with the revision
at port 18080; dedicated port-18081 verification server was stopped. No recurring
provider scheduler or metered Agent work is running.
Initial pre-revision probe returned an Amazon internship with zero known fields. The
fixed real engine now yields nine known facts and useful preparation; quota/source
gaps remain. Exact original user browser failure was not supplied.
Evidence: docs/research/scout-reassessment-evidence.md. Preserve existing saved plans.
No further browser-reproduction block is warranted without exact failing steps.

After the discovery-to-preparation gate, read docs/delivery-flags.md. Codex showed the local app, evidence and selective simulation;
Sarvesh's own technical explanation and verification remain pending. Resolve hosting
and a protected database endpoint, implement public controls, then prepare deployment,
recorded video and exact submission package. Vercel was discussed, not selected or
deployed; process-local locking needs attention for multiple function instances.
No broad research or provider switch is needed. Configure both provider keys on the
deployment host without exposing them.

## Flagged remaining work

- **Consolidated flags:** docs/delivery-flags.md includes delivery, Vercel/database,
  public-use controls, event uncertainty, product limits, authorization and compute.
- **Required delivery:** public repository, recorded demo video, complete final README/form
  and verified submission receipt. Nothing has been published or submitted.
- **Preferred delivery:** public deployment; hosting account and DB endpoint needed.
- **Quality before public use:** request limits, clear shared-demo boundaries or session
  isolation, and clean hosted setup verification. Current app is a synthetic local demo.
- **Participant contribution:** Sarvesh's technical walkthrough and verification remain pending.
- **Event uncertainty:** submission opening/edit policy, formal rubric/demo limit and blog method.
- **Compute:** Scout engine revision, deployment and video are substantial remaining blocks. Estimate and flag
  the work before extensive new agent runs, broad research or rendering. Do not repeat
  successful tests unless a concrete change or failure requires it.
- **Running locally:** resume found API/Docker stopped, restored them, and observed
  accepted-plan recovery and selective simulation. API at 127.0.0.1:18080 and persistent
  FalkorDB remain running. No scheduled background task or active agent work exists.

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
