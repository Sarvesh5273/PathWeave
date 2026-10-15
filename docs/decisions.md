# Decision log

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
