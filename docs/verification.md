# Verification report

Recorded during the build begun October 15, 2026; latest local checks October 16 IST.
Results describe this synthetic demo, not student selection or adoption outcomes.

## Measured results

- Full suite: **133 passed in 1.87 seconds**, including real disposable FalkorDB graphs.
- 24 graph, 58 source, 43 planner, 3 agent and 5 API-refresh regression cases.
- One Starlette TestClient deprecation warning; tests completed successfully.
- Real TinyFish backend Search returned ten results; official EPFL/OIST Fetch succeeded.
- Groq authenticated. Qwen 3.8 27B performed inspect_requirements, inspect_saved_plan
  and propose_plan in a successful **1.69-second** live run.
- Early Groq runs hit a token quota on call three. Measured calls one/two succeeded;
  context compaction reduced repeated payload while preserving rules and blockers.
- Accepted plan survived FalkorDB container restart with completed CV and 35 tracked
  fact versions preserved.

Automated provider responses use fixtures; live provider claims above come from
separate genuine calls. Keys were never printed.

## Browser evidence

Verified database connection, selected targets, weekly plan/exam blackout, explicit
synthetic recommendation receipt, live source refresh, and separate-graph simulation.
The simulation changed one OIST target and three tasks while preserving completed base
work. Accepted plan recovered on reload after restart. Responsive layouts were inspected
in the available browser; exhaustive cross-device testing was not performed.

Full invalidation paths are in the simulation API's impact.paths. The evidence panel
currently displays the revised plan's paths and source fragments.

## Review repairs

Independent code review found real gaps beyond the initial tests:

- Completion uncheck ignored; invalidated completion could resurrect.
- Missing cohorts left old facts current after partial refresh.
- Newly discovered hard conditions bypassed stale acceptance.
- Oversized agent messages lost useful grounding.
- B.E./B.Tech was wrongly compared against academic subject.
- Missing UI refresh/receipt actions and inaccurate rejected-call trace.
- Failed supporting-source evidence could move to the wrong source URL.

These were fixed and covered by regression cases. Test counts alone were insufficient.

## Reproduce

Run with Docker available:
```bash
REQUIRE_FALKORDB=1 .venv/bin/python -m pytest -q
.venv/bin/python scripts/proof.py
.venv/bin/python scripts/proof_live_agent.py
.venv/bin/python scripts/proof_restart.py
```

Live-agent proof consumes provider quota. Restart proof restarts this project's DB.

## Limits and unfinished delivery

Readiness and eligibility remain partial. Scheduling uses estimated effort and evenly
spread weekly availability. External receipt cannot be assumed. Generic source pages
remain partial; no exhaustive discovery or unrestricted eligibility claim.
Simulation is labeled; no real application/email is sent. Free LLM quotas remain.

Public deployment, hosted reproducibility, recorded demo, Sarvesh's technical walkthrough
and event submission are pending.

