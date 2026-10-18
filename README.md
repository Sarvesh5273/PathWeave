# PathWeave

**Discover internships. Build your preparation path.**

Built by team **Just_Chill** for Graph Hacks: Context for AI Agents.

**Latest authored v0.7.0:** explore interests through12illustrative company/research projects,
edit or retake suggestions, then use visible search settings. Selected locations and
stipend+accommodation+round-trip-travel coverage require source evidence. Unconfirmed
records have a separate view. Selected source skills now feed a shared FalkorDB topic
roadmap with prerequisite/resource edges and self-reported topic checks. Students can
edit daily availability, multiple exam weeks and holidays; the deterministic planner
protects those dates. ICS/file import, exact clock-time slots and quizzes are not included.

**Status:** source candidates appear first, followed by bounded Groq requirements
and preference scoring. Search planning/deduplication/strict filters use code rules.
Sourced requirements feed selected FalkorDB plans; incomplete coverage stays visible.
See [repair checkpoint](docs/hackathon-build/discovery-repair.md) for checks and limits.
Normal use now accepts editable user profiles and browser-scoped plans. Example and
policy-simulation controls are removed from the main interface and disabled by default.
Full Scout parity, reliable enrichment for every source and hosted delivery remain pending.
Primary entry track:
**Agents That Act on Connected Data**. Public deployment and submission video are pending.

Students select public-source internship targets, build one preparation plan, and
review what changes when a requirement changes. FalkorDB holds the requirements,
prerequisites, source versions and plan dependencies; Groq selects tools and explains
their results. TinyFish supplies genuine live Search/Fetch.

Current flow: project-based interest exploration → editable search preferences →
TinyFish Search/Fetch and bounded named-company Agent fallback → sourced requirements
and Groq preference fit → select up to three targets → self-reported topic ratings →
shared prerequisite-ordered roadmap → editable daily hours, exam weeks and holidays →
preparation, progress and replanning. Missing evidence remains explicit.

## What works

- Source discovery and refresh with checked time, cohort, source excerpts and explicit unknowns.
- EPFL, OIST, Mitacs and Google FDE adapters; other results remain partial.
- General source-bound qualification extraction and reviewed skill preparation;
  arbitrary skills without reviewed recipes remain explicit verification tasks.
- Browser-scoped hunts, run-stage traces, advisory match ranking, save/hide and reruns.
- Optional activity-interest suggestions; editable preferences, not an aptitude score.
- Up to three targets, one shared budget, per-day availability, multiple exam weeks and holidays.
- FalkorDB topic/prerequisite/resource relationships and a shared learning roadmap.
- Editable topic self-ratings choose a suggested starting point; they do not assess competence.
- Shared CV/transcript base work, distinct final documents and external receipt blockers.
- Selective fact-change impact, stale-proposal rejection and immutable plan history.
- Explicitly labeled policy simulation in a separate graph.
- Real Groq tool calls with trace; accepted state survives database restart.

Enter your own background, weekly availability and exam week. Unknown profile fields
start blank; completed work and external receipts are explicitly self-reported.
No personal documents are uploaded. Plan acceptance saves preparation, not an internship application.

## Local setup

Prerequisites: Python 3.12+, Docker Desktop/Engine and Compose.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
docker compose up -d
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 18080
```

Add `GROQ_API_KEY` and `TINYFISH_API_KEY` to `.env` or the server environment.
The file is Git-ignored. The default model is `qwen/qwen3.8-27b`; set
`GROQ_MODEL` to another available model if needed. Credentials stay server-side.

Open `http://127.0.0.1:18080`. FalkorDB Browser is `http://127.0.0.1:13000`;
the local database port is 16379. The Compose service binds these ports to loopback
and persists data in the named `graph-data` volume. No FalkorDB Cloud account is
needed for this local setup.

Choose **I know what I’m looking for** or the optional activity explorer. Enter roles
and places; use **Fine-tune your search** for organizations/visa/funding preferences.
Click **Find opportunities**. Review the actual stage trace and source evidence,
then select at most three listings and **Continue to preparation**. Set your hours/exam
week and **Build my plan**. Match scores are preference
relevance, not eligibility or selection probability. No fee/funding assumption guarantees
zero expense. Approximate deadlines remain approximate and do not certify scheduling.

Existing `.env` users: do not overwrite credentials. New discovery settings are optional
in `.env.example`. Agent and recurring refresh are disabled by default. The user-approved
$3 Agent proof ceiling does not authorize a top-up or an uncapped run; account-specific
`max_steps` support must be verified before enabling that provider path.

For isolated developer tests only, set `ENABLE_DEMO_TOOLS=true` to enable the legacy
cached-example/simulation APIs. Normal UI has no such controls. Historical example scenario: select
EPFL Summer 2027 and OIST Fall 2027 to demonstrate future preparation. Their portal
states remain truthful; a future deadline does not mean applications are open.

## Verification

```bash
REQUIRE_FALKORDB=1 .venv/bin/python -m pytest -q
.venv/bin/python scripts/proof.py
.venv/bin/python scripts/check_providers.py
.venv/bin/python scripts/proof_live_agent.py
.venv/bin/python scripts/proof_restart.py
.venv/bin/python scripts/proof_scout_engine.py
```

The live-agent check uses Groq tokens; provider checks use real APIs.
`proof_scout_engine.py` is a bounded real Search/Fetch/Groq + disposable graph proof,
with Agent disabled. For mock-backed browser regression checks, install the optional
Playwright development tool (`pip install -e '.[ui]'`) and run
`scripts/check_discovery_ui.py --url http://127.0.0.1:18080`; this is not live-provider proof.
The restart proof restarts only this project's FalkorDB container.
Do not remove the named volume if you want to preserve plans.

**v0.7.0 verification:** the implementation agent recorded **819 passing local tests**,
including disposable FalkorDB cases, and a focused browser fixture covering daily
availability, protected dates, roadmap resources and rating-triggered replanning.
Earlier real TinyFish/Groq source proofs were partial; this does not establish reliable
extraction from every website. See [roadmap verification](docs/hackathon-build/roadmap-implementation.md)
and [discovery limits](docs/hackathon-build/discovery-repair.md).

## Graph and architecture

[Actual graph model and queries](docs/graph-model.md) ·
[Demo walkthrough](docs/demo-walkthrough.md) ·
[Technical spec](docs/hackathon-build/spec.md)

Key files:

- `app/sources.py`: public source adapters and TinyFish client.
- `app/discovery/`: Scout-inspired collection, extraction, ranking, browser, engine,
  durable hunt/queue/accounting state and selected-listing preparation bridge.
- `app/graph.py`, `queries/`: versioned graph storage, prerequisite closure and reverse impact.
- `app/recipes.py`: explicit preparation estimates and document compatibility.
- `app/planner.py`: deterministic allocation and conservative readiness states.
- `app/agent.py`: bounded Groq tool loop and evidence summaries.
- `app/main.py`, `app/static/`: API and browser interface.

## Limits that matter

Scheduling uses per-day capacity when supplied; otherwise it spreads weekly hours
across seven days. Effort is estimated. Unknown deadlines, external receipt and unsupported criteria prevent certainty.
The app does not certify complete eligibility. Source adapters are deliberately bounded.
Generic pages do not acquire invented conditions. Rate limits can pause agent narration;
the deterministic plan remains accessible.

The local server scopes plans and hunts to a browser bearer token. This is not a user
account or cross-device login; clearing browser storage loses the token. Hosted use needs
server-side provider secrets, protected database access and appropriate rate controls.
Public source facts are shared; profile and progress payloads are stored in local FalkorDB
and returned only through the matching browser's plan routes. Use synthetic inputs for
the hackathon recording until the event's personal-data restriction is clarified.
Discovery hunts/cache/jobs/usage persist in ignored `data/runtime/scout.sqlite3` by
default. FalkorDB remains the graph reasoning/evidence/plans store. This architecture
requires persistent local disk and a single hosting process; it is not a verified
multi-host/serverless queue. Public showcase/reviewer-reserve parity remains unfinished.

## Planned development

The current version delivers manual availability, self-reported topic levels and a
reviewed starter roadmap. The next development areas are:

- **Timetable import:** editable weekly and semester schedules from images, PDF or ICS.
- **Knowledge checks:** small topic checks and practical exercises beyond self-ratings.
- **Richer preparation:** broader reviewed learning resources and source-supported
  company/research selection-stage guidance.
- **Calendar planning:** clock-time study sessions, exam buffers and conflict handling.
- **Discovery reliability:** broader source coverage and better selective extraction/rechecks.
- **Progress adaptation:** clearer replanning when work, targets or availability change.
- **Hosted access:** secure accounts, cross-device recovery and durable protected storage.

These are planned directions, not implemented features or promised release dates.
The [full product handoff](docs/project-handoff.md) separates the original vision,
implemented behavior, verification limits and remaining submission work.

## AI disclosure and participant contribution

Codex and delegated coding agents researched, planned and implemented the project.
AI coding agents authored the implementation and tests with root integration and
code review; it is not claimed as entirely human-written code. Scout is Sarvesh’s
pre-event discovery reference; this repository’s graph preparation and roadmap work
was built during the event. See the contribution journal for provenance.
An independent review found defects that were fixed and regression-tested.
Sarvesh supplied the domain vision, requirements, safeguards and scope decisions.
His technical walkthrough and final verification are still pending; do not claim those
have occurred. [Contribution journal](docs/hackathon-build/build-notes.md).

## Project continuity and event

Read [task.md](task.md), [decisions](docs/decisions.md) and [scope](docs/hackathon-build/scope.md)
to resume. The official event closes October 18, 2026, 23:59 IST.
[Rules](https://www.wemakedevs.org/hackathons/falkordb/rules) ·
[Overview](https://www.wemakedevs.org/hackathons/falkordb) ·
[Review](docs/hackathon-review.md).

Source commits have been pushed to the PathWeave GitHub repository. A demo video
and final event submission remain pending; no submission receipt is claimed.
