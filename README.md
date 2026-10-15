# Just Chill — Internship preparation with connected context

**Status:** working local MVP for Graph Hacks. Primary entry track:
**Agents That Act on Connected Data**. Public deployment and submission video are pending.

Students select public-source internship targets, build one preparation plan, and
review what changes when a requirement changes. FalkorDB holds the requirements,
prerequisites, source versions and plan dependencies; Groq selects tools and explains
their results. TinyFish supplies genuine live Search/Fetch.

## What works

- Source discovery and refresh with checked time, cohort, source excerpts and explicit unknowns.
- EPFL, OIST, Mitacs and Google FDE adapters; other results remain partial.
- Up to three targets, one weekly time budget, protected exam weeks.
- Shared CV/transcript base work, distinct final documents and external receipt blockers.
- Selective fact-change impact, stale-proposal rejection and immutable plan history.
- Explicitly labeled policy simulation in a separate graph.
- Real Groq tool calls with trace; accepted state survives database restart.

The demo uses a **synthetic student**. No personal document upload, internship application
submission, aptitude score, selection prediction or unrestricted eligibility engine exists.

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

Load sourced examples for an explicit cached starting point, or search live. Select
EPFL Summer 2027 and OIST Fall 2027 to demonstrate future preparation. Their portal
states remain truthful; a future deadline does not mean applications are open.

## Verification

```bash
REQUIRE_FALKORDB=1 .venv/bin/python -m pytest -q
.venv/bin/python scripts/proof.py
.venv/bin/python scripts/check_providers.py
.venv/bin/python scripts/proof_live_agent.py
.venv/bin/python scripts/proof_restart.py
```

The live-agent check uses Groq tokens; provider checks use real APIs.
The restart proof restarts only this project's FalkorDB container.
Do not remove the named volume if you want to preserve plans.

**Recorded results:** 133 regression tests passed; live TinyFish Search/Fetch passed;
a real Qwen tool workflow passed in 1.69 seconds; accepted plan recovered after
database restart. See [verification report](docs/verification.md) for scope and limits.
Unavailable database tests fail when `REQUIRE_FALKORDB=1`.

## Graph and architecture

[Actual graph model and queries](docs/graph-model.md) ·
[Demo walkthrough](docs/demo-walkthrough.md) ·
[Technical spec](docs/hackathon-build/spec.md)

Key files:

- `app/sources.py`: public source adapters and TinyFish client.
- `app/graph.py`, `queries/`: versioned graph storage, prerequisite closure and reverse impact.
- `app/recipes.py`: explicit preparation estimates and document compatibility.
- `app/planner.py`: deterministic allocation and conservative readiness states.
- `app/agent.py`: bounded Groq tool loop and evidence summaries.
- `app/main.py`, `app/static/`: API and browser interface.

## Limits that matter

Scheduling spreads weekly availability evenly across seven days and uses estimated
effort. Unknown deadlines, external receipt and unsupported criteria prevent certainty.
The app does not certify complete eligibility. Source adapters are deliberately bounded.
Generic pages do not acquire invented conditions. Rate limits can pause agent narration;
the deterministic plan remains accessible.

The local server is a single synthetic demo workspace with one worker. Hosted use needs
server-side provider secrets, protected database access and appropriate rate controls.
A shared anonymous demo must not be represented as a private multi-user product.

## AI disclosure and participant contribution

Codex and delegated coding agents researched, planned and implemented the project.
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

No public repository publication or event submission has been performed.

