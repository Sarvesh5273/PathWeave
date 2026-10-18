# Decision log

October18navbar follow-up: user screenshot showed header/footer wider than decision
content. Header/footer now follow the same880pxdecision-screen width; working screens
retain1120px. CSS-only alignment correction; no browser run.

## D033 — Remove starburst branding and constrain desktop widths

October18,2026,IST: Sarvesh's screenshot showed the five-step entry still stretched
across desktop. Root removed starburst marks from logo, explorer and footer and
replaced the exploration icon with a question mark. Direction/search/time screens
use an880pxmaximum; results/roadmap allow1120px. Entry cards have balanced height,
mobile stacks them, and saved shortcuts sit below the heading. Syntax/control-ID
checks passed; no browser or visual verification performed per user instruction.

## D032 — Screenshot-led five-step UX redesign

October18,2026,IST: Sarvesh rejected the overall UX while retaining the cream/orange
theme, explicitly requested no browser runs, and suggested storytelling one step at
a time. Root replaced the landing/dashboard hierarchy with Direction → Search →
Targets → Your time → Roadmap. Stage-specific headings, saved-search/roadmap entries,
back/edit controls and separate source-evidence view retain the existing backend.
Larger readable typography, custom select styling, compact results controls and
collapsed secondary settings reduce competing actions. No shadcn/React migration.
JavaScript syntax, HTML nesting, unique IDs and fixed control references checked;
no browser visual/interaction verification or provider calls claimed. User visual
feedback is next; public delivery remains pending.

## D031 — Focused UI motion pass

October18,2026,IST: Sarvesh requested shadcn-like animations. Root added lightweight
CSS/Web Animations API entrance, hover/press, page-transition and active-progress
effects without a React migration or new dependency. Reduced-motion preferences
disable effects. Local navigation/styles checked; no browser JavaScript errors
observed. No provider calls or plan mutations. Footer branding corrected to PathWeave.

## D030 — PathWeave name accepted; manual repository publication

October18,2026,IST: Sarvesh selected PathWeave and “Discover internships. Build your
preparation path.” Just_Chill remains the team name. User authorized source publication,
then chose to perform it through the configured VS Code GitHub account. Local UI,
API title, README and graph documentation updated. Publication is not yet verified.

## Naming clarification — October18,2026,IST

Sarvesh clarified that Just_Chill is the team name, not the project name. The project
name is still pending selection. Existing Just Chill UI/README branding is provisional;
do not publish it as the confirmed product title or change branding without a choice.

## D029 — Implement graph learning roadmap and editable timetable

October 18, 2026, IST. With roughly four hours remaining, Sarvesh asked root to
implement the agreed product plan and expressed confidence in root's technical
execution. Root implemented v0.7.0: source facts map to shared FalkorDB topics,
topics carry prerequisite/resource edges, self-ratings choose a suggested starting
point, and deterministic scheduling accepts per-day availability, multiple exam
weeks and holidays. Ratings remain self-reports and authored resources remain
guidance; neither certifies knowledge or changes source requirements.

Final full local gate:819passed in4.03s plus a focused offline browser check.
No provider call, paid Agent, deployment, publication or submission. Saved hunts,
plans and Groq configuration were preserved. Calendar-file import, clock-time slots,
quizzes and broad interview curricula remain explicit limits. Details:
hackathon-build/roadmap-implementation.md.

## D028 — Restore progressive discovery with Groq; retain roadmap requirements

October17–18,2026,IST: Sarvesh accepted restoring Search/Fetch/Agent with Groq
extraction/scoring and reminded root to preserve listed requirements for the later
roadmap. v0.6authored pipeline keeps early candidates, sourced required/preferred
facts and strict conditions separate from preference fit.243affected checks passed;
saved-source graph proof27facts/5tasks/67paths, cannot_certify. Details and incomplete
work: hackathon-build/discovery-repair.md. Main app restarted; UI review remains.

Sarvesh proposed Gemini after failures, then accepted keeping Groq if warranted.
Keep Groq; no migration or Gemini proof performed. Strict JSON-schema mode remains
an optional focused repair. Root acknowledged excessive repeated live checking and
scope expansion after user flagged time/compute. No further broad provider proofs.
No new paid Agent run, agents, deployment, publication or submission.

## D027 — Scout pipeline clarified; discovery reliability takes priority

October 17, 2026, IST. Sarvesh reiterated the desired Scout discovery flow: rule-based
Search, batched Fetch, named-company unreadable-portal Agent, page extraction and
match scoring, with Groq replacing the Replit LLM. This is broader than the current
BasicDiscoveryEngine default. Root inspected code: discovery ranking passes settings=None;
generic extraction waits for selection; default Agent links are not followed through
the full read/extract stage. The older engine includes these stages but is not a
verified replacement merely because it exists.

Root recommends repairing discovery and evidence extraction before timetable/roadmap
work: early candidates remain visible, source details progressively enrich, Agent-returned
posting links feed Fetch/extraction, and Groq scoring is restored within bounded quotas.
No claim of reliable extraction across every arbitrary website. Verify supported source
families and explicit failure/unknown handling with live cases.

Preference score proposal: user must-haves remain gates; optional preferences can
contribute an explained score separate from syllabus readiness and evidence completeness.
Japan and three-component funding remain strict under D025/D026 unless Sarvesh explicitly
relaxes them. A score cannot compensate for missing evidence or a failed must-have.
This score design is advice under discussion, not an implemented or accepted change.
No application code, paid Agent call or new provider hunt in this discussion.

Current state: historical local MVP verification complete; Sarvesh has reopened the
product decision after reporting a poor discovery/preparation experience. The bounded
independent reassessment is complete; Sarvesh accepted revision and requested Scout
engine parity. The first new preference/query-planning slice is implemented/tested;
the full engine and API/UI integration remain unfinished.
Public deployment, recorded video, participant
walkthrough and submission remain pending. D014, D016 and task.md describe current behavior;
earlier dated entries preserve history and are not instructions to undo progress.

## D001 — Source of truth (Oct 15)

Confirmed: WeMakeDevs official event rules, schedule and FAQ are the event sources.
The registered panel supplied by Sarvesh is useful account-specific evidence, but
its conflicting submission time still needs verification. Do not switch to Devpost.

## D002 — Durable context (Oct 15)

Confirmed by user: keep project docs and task.md so context survives a new chat.
task.md is the progress source; this file is the decisions source.
AGENTS.md preserves the user's advisor instructions.

## D003 — Technical ownership (Oct 15)

Confirmed by user: Codex should decide the technical part.
User prefers free API options, naming Groq.
This does not authorize paid upgrades or provide an API credential.

## D004 — Research agents (Oct 15)

Confirmed by user: agents are optional at Codex's discretion.
One read-only agent researched primary FalkorDB docs and existing projects.
No agent has built or modified the application.

## D005 — Provisional stack (Oct 15)

Recommendation: direct FalkorDB Python client, FastAPI, a lightweight web UI,
one tool-calling LLM, parameterized Cypher and 4–6 bounded tools.
Groq is preferred; exact model, versions, UI library and deployment are pending
the product requirements and a setup spike. No runtime is verified yet.

## D006 — Product and track

Sarvesh supplied an internship discovery/preparation vision and explicitly permits
a new idea if that is the stronger choice. Original vision is saved in user-idea.md.
Codex recommends keeping the domain and narrowing the MVP to evidence-backed shared
preparation and source-change replanning. Primary track recommendation: Agents That
Act on Connected Data. Sarvesh subsequently accepted the narrowed direction and
requested an independent review before implementation.

## D007 — Data and contribution

Recommendation: synthetic nonpersonal data first, due to the event's restrictions.
Record human product choices, work, verification and code understanding accurately.
AI use must be disclosed.

## D008 — Timeline

Official closing time: Oct 18, 2026, 23:59 IST.
Proposed internal target: Oct 18, 20:00 IST.
Submission opening and edit policy remain unresolved; no first-submission action
until team and complete form are concrete and authorized.

## D009 — Proposed internship MVP (Oct 15)

Draft scope: real bounded TinyFish discovery, explicit selection of up to three targets,
typed eligibility and deliverables, shared prerequisite graph, one weekly capacity
budget, exam protection and explained revisions. Defer the general taste test and
comprehensive global coverage. Preserve the full user vision as future direction.

## D010 — Graph and scheduling responsibilities (Oct 15)

Recommendation: FalkorDB traverses requirements, reusable task prerequisites and
source-change impact. Deterministic code allocates time. Similar document names alone
cannot establish compatibility. Synthetic scenarios stay distinct from official facts.
No runtime graph query or planner implementation has been verified yet.

## D011 — Independent review requested and scope accepted (Oct 15)

Sarvesh said “ok i agree” to the narrowed internship proposal and asked for a fresh
independent agent to challenge the idea and hackathon strategy. A fresh reviewer was
started without inherited conversation history. It has read the project documents
and independently checked sources. The narrowed direction is accepted; improve its
demo and implementation criteria based on review rather than re-requesting acceptance.

Completed researchers may stay listed for reuse; they are not executing. Sarvesh
explicitly requested keeping them listed after clarification. The reviewer must finish
its bounded report and remain completed until assigned another task.

## D012 — Independent review incorporated (Oct 15, 22:10 IST)

Reviewer verdict: revise, then conditional go; keep internship domain. Parent accepts
the objection that the original hours-arithmetic demo is too weak as the headline.
Use real program exceptions, external recommendation receipt and selective fact-change
impact to drive proposed actions. Preserve unaffected and compatible completed work.
Readiness quizzes are deferred; two targets lead the demo. Source facts, self-reports,
planning estimates and simulated policy changes must be distinguishable.

Both research agents completed. No application code or runtime validation exists yet.
The next task is PRD/spec/checklist and the proof-gate slice. Do not re-request approval
of the narrowed direction; Sarvesh already supplied it.

## D013 — Implementation authorized and roles split (Oct 15)

Sarvesh requested starting implementation with independent agents and root review.
Shared models, PRD, spec and checklist were written before delegation. Root owns API,
agent loop and UI; three agents own graph, sources and planner separately.
Python 3.12 and explicit pinned dependencies installed. FalkorDB 6.0.2 in local Docker
is bound to loopback ports 16379/13000 with persistent data at /var/lib/falkordb/data.
Local Docker satisfies the event hosting rule; a live deployment remains preferred.
Groq key was supplied in ignored .env and verified by presence only. TinyFish key is
present in the execution environment; no secrets have been copied to project docs.


## D014 — Verified local build and provider choice

The actual Qwen 3.8 27B account model is available and the real tool loop passed.
Repeated long context caused an observed token-per-minute rejection; context was
reduced without removing target states, reference rules, blockers or next action.
Groq remains primary; Gemini was considered but is unnecessary for the current proof.

Source corrections use scoped semantic fact versions and a graph-derived hard-requirement
membership guard. Completed work is normalized to prevent stale resurrection.
External receipt events include required reference count/channel. Public facts,
synthetic profile, simulation, estimates and graph metadata remain distinct.

Local runtime tests, browser workflow and DB restart passed. Public delivery still
requires a host/database setup and server-side provider secrets. TinyFish is available
from the execution environment; only Groq is in the project's ignored .env.

## D015 — Resume inspection and requested stop (October 16, 2026, IST)

Sarvesh resumed, requested a walkthrough and delivery work, asked for a free hosting
route and raised Vercel. Current official documentation supports our FastAPI entrypoint;
deployment remains conditional on cross-instance coordination and a protected database.
The free FalkorDB plan page lists no TLS/continuous persistence/backups; the actual
endpoint and durability are unverified. No host was selected or deployed.

Codex restored stopped Docker/API, observed accepted-state recovery, showed the app
and a selective OIST simulation affecting one target/three tasks, then reloaded the
official plan. This does not establish Sarvesh's technical understanding or verification.

Sarvesh objected to compute use and instructed Codex to list all flags in docs and stop.
Work is paused; docs/delivery-flags.md consolidates the outstanding work. No code change,
new agent run, full test rerun, rendering, publication or submission occurred.

## D016 — Product reassessment requested (October 16, 2026, IST)

Sarvesh supplied Scout's public website and repository, reported that Just Chill is
not working as intended and appears limited to hardcoded programs, and asked for an
independent continue-versus-change assessment. This authorizes a bounded review, not
a wholesale rebuild, deployment, external message, paid service or publication.
The earlier narrowed-scope acceptance is historical; his new feedback must be addressed.

Root found a real live-discovery path and tested one non-example query without graph
writes. Amazon was retrieved but all 24 structured fact fields remained unknown;
Indeed was bot-blocked. Historical tests do not establish general discovery utility.
The exact reported browser failure remains unverified. Evidence:
research/scout-reassessment-evidence.md. One independent read-only reviewer was launched
and subsequently completed, as recorded below.

Official rules again confirm local Docker/self-hosted/Cloud are accepted. Cloud was
not mandatory; free Cloud docs explicitly lack TLS, persistence and backups. Scout's
reviewed commit is dated October 13, before the event start. Preserve its pre-event
provenance and do not claim wholesale reuse is approved by the organizer.

The reviewer completed and independently recommends material revision toward Scout's
actual discovery followed by preparation, retaining the current graph/planner contracts.
Root checked the key code evidence and concurs. Sarvesh clarified that actual Scout
behavior is the product bar, not just a similar-looking search screen. Evidence and
alternatives: independent-product-reassessment.md. All reviewer work is completed.

This is a recommendation, not an implemented scope change or promise of winning.
Write revised acceptance criteria and a bounded estimate before substantial coding.
The reviewer's 6–10-hour estimate covers a thin end-to-end slice, not full parity or
delivery. Do not start a 45–90-minute investigation of unspecified browser errors.

Sarvesh then clarified the intended reuse boundary: take inspiration from Scout and
replicate its workflow. Treat this as inspiration-led new implementation, not a request
to transplant its pre-event source. Inspiration is not the same as wholesale reuse;
do not require organizer approval merely for adopting that product workflow. Preserve
provenance if actual old code is incorporated. No app changes have been made yet.

## D017 — Revised direction accepted; exploration proposed (October 16, 2026, IST)

Sarvesh explicitly agreed to inspiration-led Scout discovery followed by preparation.
This is the accepted revised product direction; do not ask him to accept it again.
The detailed acceptance checklist, estimate and implementation remain unfinished.

He then asked whether the first user-facing step should include gamification for
students who do not know their interests. This revives the original exploration idea
in research/user-idea.md; it is a design question, not authorization to implement a
full assessment. Root recommends an optional, short activity-preference explorer
with a skip path and editable suggestions, not aptitude/selection/validated career
scores. Proposed onboarding should not delay a working discovery-to-plan core.
The exact exploration feature and scope are not yet accepted or implemented.

## D018 — Preserve Scout engine; first implementation slice (October 16, 2026, IST)

Sarvesh agreed to optional interest exploration and explicitly requested replicating
Scout's engine as considered, including TinyFish Agent and the other features. He
permits gaps to be flagged. Preserve the actual discovery stages and behavior, not
just a similar screen or a single-query search. Use inspiration-led new implementation
as clarified earlier; leave the original Scout source unchanged. See scout-parity.md
in hackathon-build/ for the complete acceptance/stage map and separately flagged gaps.

Root implemented new Python preference/work-ceiling contracts and preference-driven
query planning. It preserves query order, roles/places, research/company, sponsorship,
funding hints, keywords/citizenship and Scout's search-domain policies. Independent
review found no query-planning blocker, but found a missing soft/hard deadline-order
guard; root fixed it and added tests. Final targeted run: 25 passed. No paid Agent,
new Groq call, full suite rerun, graph mutation, server restart or endpoint switch.

Agent remains part of the planned automatic pipeline, not removed. Runtime metered
use needs an authorized configured budget; after that, do not add an unrequested
per-call confirmation barrier. Scout's Replit-billed AI requires adaptation to the
preferred Groq boundary, with differences explicit. Approximate-deadline/funding/
evidence assumptions are flagged, not silently certified in preparation.

Full engine parity, typed general requirements, UI/hunts/queue/refresh integration and
delivery remain unfinished. The 6–10-hour thin-slice estimate is not a full-parity
estimate. No running agent or scheduled provider work remains from this slice.

## D019 — Parallel implementation and $3 Agent authorization (October 16, 2026, IST)

Sarvesh requested implementation with parallel agents and invited needed input questions.
Root froze contracts and split source/ATS, AI extraction/ranking, transport/browser,
preparation bridge; root owns engine/state/queue/API/UI. All four initial jobs delivered.
A fresh bounded reviewer found concrete queue/refresh/state/Agent-cap/deadline defects;
follow-up corrections/tests are active, not a broad research block.

Sarvesh authorized **up to $3 total** metered Agent proof from existing credits, not
a top-up/subscription. Duration is not an enforceable spend cap. Live Agent remains
disabled until a supported transmitted hard step/spend cap is verified. Implement its
automatic fallback/cache/recovery and show the gate. No paid Agent request occurred.

A fresh real Amazon Fetch → Groq extraction succeeded in 2.96 seconds with exact
quotes for degree fields, language alternatives and CS fundamentals. Generic selection
→ graph → plan API testing exposed an old default-store binding; root corrected it.
Three API tests passed after correction using a disposable real FalkorDB graph. This
does not certify full search/UI/provider parity or Sarvesh's own testing.

## D020 — Core revision verified; remaining gates (October 16, 2026, IST)

All coding/review tasks completed. Root integrated the fixes and ran the full regression
gate: 586 passed in 2.85 seconds, including actual disposable graph tests. A later
worker-path regression passed separately. Prior module counts overlap this result.

The first live engine proof found a real defect: a single Amazon Summer posting also
describes optional Winter/Fall start dates; the bridge discarded all common qualifications.
Root repaired that specific scope distinction, retained other-round rejection, and
added tests. Location-aware lead prioritization was added before bounded collection.
A repeated proof for those concrete changes passed in 11.42s: three real searches,
eight fetch URLs, two extraction attempts, two listings; German Amazon target yielded
nine known typed facts, 21 tasks and 82 graph evidence paths. Groq quota/source gaps
were explicit; matching fell back deterministically. This is bounded proof, not full
opportunity coverage or unlimited provider reliability.

Actual browser/API/FalkorDB checks using those retrieved results (no API mocking and
no new provider requests) passed selection, skill preparation, exam protection,
unknown readiness, acceptance/reload persistence and restored hunt controls in a
dedicated verification graph/server. Mock-backed UI checks separately passed mobile,
exploration and save controls. No testing is attributed to Sarvesh without evidence.

Root restarted the main local API at port 18080 with v0.2.0 and observed its prior
latest proposal/one completed task. Main state was not replaced with the verification
plan. The port-18081 verification server was stopped. No recurring provider work,
publication, deployment or event submission occurred.

Sarvesh reported available TinyFish credit but did not know the cap/account setup.
The connected tool's wallet is not proven identical to the application's key/account;
do not use it to infer that app's balance or spending permission. The $3 total proof
authorization remains unchanged; no Agent spend. Custom step-cap support is unverified.
Public showcases/reviewer reserve parity, public hosting/delivery and participant
understanding remain gates. SQLite queue/state requires durable single-host storage;
the earlier Vercel discussion must be reassessed before deployment.

## D021 — Cream grid usability pass authorized (October 16, 2026, IST)

Sarvesh accepted a focused UI pass and authorized frontend work with cream background,
grid-like pages and orange shades. Root uses the existing HTML/JS app (no installed
frontend-specific skill) rather than introducing a framework or unrelated workflow.
Design/acceptance: hackathon-build/ui-direction.md. No discovery/planner/provider
policy change or expanded metered/publication/deployment authorization is inferred.

Entry paths, collapsed advanced preferences, actual-event run progress, grid cards,
and selection-before-time setup are authored. TinyFish browser Agent status is explicit
and separate from Groq plan review. Old style.css remains; site.css owns the new page.
Targeted browser checks and isolated actual API/graph checks are the gates; do not
report static/mock UI success as a fresh live search or Sarvesh's own verification.

Final UI gates passed: keyboard entry/explorer/skip, collapsed preferences, run-event
partial/failed states, selected/saved/hidden views, selection before time entry,
restored hunt/selection and 390px/320px overflow checks using mocked discovery.
Actual isolated API/FalkorDB using previously retrieved Amazon results also passed
plan building, shared/category task filters, source/evidence pages, protected exam
week, acceptance/reload and mobile layout. No fresh Search/Fetch/Groq/Agent calls,
no main graph writes and no unrelated backend suite rerun for this frontend pass.
Verification server stopped; main UI is served at 18080 without a backend restart.

## D022 — Discovery readiness withdrawn; actual Scout repair (October 16, 2026, IST)

Sarvesh again reports discovery does not work like Scout and notes no TinyFish key
in .env. Root verified: no file entry, but the app inherited a configured key. Root
saved that existing key into ignored .env and verified a fresh process can load it
with TINYFISH_API_KEY removed from its environment. No key or secret was printed;
no supplied Groq value was overwritten. This repairs portability, not discovery quality.

Actual main-state Japan software/robotics hunts show zero/one listings, failed ATS
feeds, source gaps and a Groq rate rejection followed by skipped extraction. Earlier
partial Amazon/cached browser gates do not meet the accepted Scout replication bar.
Readiness claim withdrawn; user need not supply the same brief or diagnostics again.

Two bounded parallel agents repair collection/feed evidence parity and Groq token/
rate admission respectively; root integrates and verifies an actual browser-started
fresh hunt rather than loading previous result fixtures. Original Scout main hash was
rechecked and unchanged. Preserve the cream UI, actual graph preparation and saved
plans. Keep original-code provenance and no fabricated full-parity or win claim.
The $3 total Agent ceiling remains; safe capped account validation may be attempted,
but no uncapped fallback or new account/top-up is authorized.

Follow-up source/account evidence resolves the custom-beta gate for one safe test:
official run docs specify a 150-step default when max_steps is omitted, and read-only
GET/v1/wallet with the actual app key confirms USD0.016 per Agent step. One default
run's maximum2.40USD fits the existing3USDauthorization. The app-key wallet matched
the tool wallet on this read; earlier nonlinkage was a verification gap, now resolved.

Root added a separate verified-default mode (only valid at150steps) and performed one
BrowserFallback proof on Notion's public Ashby board. It completed and returned three
software internships, reported3steps. The full2.40 reservation remains conservative;
no extra paid run or claim of exact billedcost from reportedsteps. Credentials and
defaultcap configuration are now local in ignored.env. No account change/topup/cancel
or uncapped retry occurred. This verifies Agent transport, not full Scout parity.

## D023 — Source-first discovery, AI only after selection (October 16, 2026, IST)

Sarvesh asked why even a basic filter fails and said to forget Scout. Root agrees the
architectural error is gating basic listing cards on complete LLM extraction. New
default BasicDiscoveryEngine uses Search, public feed/posting metadata and deterministic
role/location relevance with no LLM calls. Unknown visa/funding/application requirements
remain visible rather than suppressing a sourced candidate. The old full AI-first engine
is preserved, not deleted or called equivalent. Detailed extraction follows selection.

Progress is stored per run, separate from completed hunt results, so early cards do
not erase previous history/new flags. Public search leads are labeled unverified;
feed/posting metadata is distinguished from eligibility. Existing planner/schema and
cream UI remain. 139 targeted cases passed before the actual fresh Japan proof and
independent read-only review, which are pending. No paid Agent/upgrade was started.

Source-first gates now passed: fresh browser-started software/robotics Japan hunt,
no mocked responses or loaded shortlist, 18 leads in58.88s with0LLM/Agent calls.
ASM Japan and HENNGE Tokyo/Japan had source location evidence; unknown-location/foreign
leads are not claimed as verified Japan matches. Save/reload passed. Early source-first
probes exposed seniority/country recognition gaps; fixed and covered before this gate.

Independent read-only review found generic internship indexes, stale/cached evidence,
cohort identity, raw feed binding and incidental place-label risks. Root fixed them
and added regression cases. Latest full gate752passed in3.79s with real disposable
FalkorDB tests. A selected HENNGE detail extraction still exceeded output constraints;
it was explicitly rejected and its target retained with unknown facts/2verification
tasks. This is proof of graceful failure, not complete source preparation coverage.

No further Agent spend/top-up. Main saved proposal/one completed task unchanged before
restart; use source-first UI feedback, then selective enrichment/reliability/delivery
work. Do not resume full Scout parity automatically against the latest basic-filter steer.

Main restart/readback verified v0.3.0, healthy FalkorDB and both keys loaded with
TinyFish inheritance removed. Saved main plan ID remained
`plan-2a549e936ef648a9bd52db417b8afe2c`, proposed, one completed task. Dedicated test
server stopped; all agents completed. No recurring or additional paid provider work.

## D024 — Actual user preparation requested (October 17, 2026, IST)

Sarvesh requested removing demo behavior to see the actual working flow. Root replaced
fictional profile defaults with editable unknown-first inputs and scoped plans to the
browser's bearer token. Cached examples/policy simulation were removed from the main
UI and are disabled by default; historical graphs and fixtures were preserved. Completion
and receipt now record explicit user reports, not synthetic events or verified delivery.

Selected-source extraction was compacted to qualifications only. First fresh HENNGE
call still reported partial coverage; root corrected the all-or-nothing behavior to
retain individually source-validated facts plus an unknown hard coverage guard. The
next fresh Fetch/Groq check returned 12 supported facts, 9 graph preparation tasks,
14 source-excerpt paths and accepted readback in a disposable real graph in 2.84s.
Readiness remained cannot-certify. No paid TinyFish Agent or new research agent ran.

131 affected planner/graph/API/agent tests passed; 135 extraction/quota tests passed.
Local personal use is supported; full source coverage, authenticated accounts, hosted
security and delivery are not claimed. Hackathon recording remains synthetic until
the event's personal-data restriction is clarified. User understanding/testing is not
inferred from Codex's tests.

Final browser proof uses a genuine fresh HENNGE/Japan hunt (8leads, source gaps), then
selection/profile/plan and restart recovery. It produced4verification/blocker tasks,
so enrichment variability remains a concrete flag despite the isolated9-task proof.
The start date now remains user-selected rather than moving backward to Monday.
Source coverage warnings persist across plan reload; time/progress edits reuse already
selected evidence. Final70affected tests passed; no further scope or paid action.

## D025 — Project scenarios and funding locked; discussion before implementation

October 17, 2026, IST: Sarvesh confirmed locking interest exploration and concrete funding
components. He clarified that scenarios should describe projects in company roles or
research internships. See hackathon-build/interest-and-funding.md. Use beginner-readable
activities, tentative explained suggestions, edit/retest and try-it activities. Real
project attribution and illustrative scenarios must remain distinguishable.

Strict funding means explicit stipend/living support, accommodation AND round-trip
travel evidence. Unknown components are not confirmed matches; show cost limits and
exceptions. This supersedes Scout's stipend plus travel-or-housing filter meaning.
Readiness/topic checks, timetable ingestion and learning-resource roadmap remain under
discussion. No application changes/tests/provider runs authorized or performed by this lock.

## D026 — Implement locked exploration and strict discovery (October 17, 2026, IST)

Sarvesh asked to start implementing after confirming the flow. Root implemented the
locked first slice: 12 illustrative project questions, explained tentative suggestions,
edit/retest, visible search settings and source-supported strict location/funding
filters. Three funding components are cumulative; unconfirmed candidates have a separate
view. Old hunts are checked using stored snapshots, not assumed newly verified.

Default search/fetch ceilings now12/45 with10URLbatches and25searches/minute; Fetch
requests one-hour provider cache tolerance. No SDK/provider/database replacement or
new paid/recurring authorization.88affected cases passed, including real isolated
FalkorDB API tests. Actual browser question/edit/retest/filter checks passed with
stored public evidence and no new provider calls. Test answers are not Sarvesh's interests.

See hackathon-build/flow-implementation.md. Timetable ingestion, readiness policy and
shared learning-resource roadmap remain separate pending design/build work. v0.5.0
main server runs; old plans preserved. Do not call the full vision or delivery complete.
