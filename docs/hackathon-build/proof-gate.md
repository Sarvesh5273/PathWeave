# Engineering proof gate

Status: core local gate passed. G01–G10 are covered by tests and genuine integrations
listed in ../verification.md. The build took longer than the proposed checkpoint,
including environment setup, independent review and cross-module corrections.
No public deployment or participant walkthrough is claimed.
Direction accepted by Sarvesh. Refined from the independent review on October 15, 2026.

## Goal

Before building the full interface, prove that real FalkorDB traversals produce a useful
action and a selective plan revision. Use a synthetic applicant and small vetted
program facts. Effort estimates, scenario dates and simulated updates stay labeled.

## Minimum slice

Application backend → real TinyFish fetch → grounded typed facts → FalkorDB queries →
deterministic plan → real LLM tool selection → proposed revision → accepted plan version.

Use two lead targets. Keep runtime API keys server-side and do not print them.
Do not assume Codex's TinyFish/Groq access supplies backend credentials.

## Evidence cases

| ID | Behavior | Expected evidence |
| --- | --- | --- |
| G01 | Real source fetch | Backend makes a genuine provider call; each extracted fact keeps URL, fragment, checked time and cohort |
| G02 | Real graph tool | Parameterized Cypher runs in FalkorDB; returned paths feed the action, not merely visualization |
| G03 | Safe shared preparation | One compatible base task shared; final program-specific documents remain distinct |
| G04 | External waiting state | OIST-like received-reference condition blocks readiness; response proposes a user task, not an automatic email |
| G05 | Capacity and exams | Combined schedule never exceeds stated weekly hours or assigns work to blackout dates; effort and waiting time differ |
| G06 | Call and criterion semantics | Closed call excluded from current applications; future opening unknown; preferences not turned into hard requirements |
| G07 | No-op refresh | Nonsemantic page change yields no changed facts and no newly stale decisions |
| G08 | Selective update | One changed fact returns exact affected decisions/tasks and paths; unrelated target and completed compatible base work survive |
| G09 | Missing/conflicting evidence | Failed fetch or uncertain extraction does not silently delete a rule or certify an unsupported plan |
| G10 | Agent and persistence | Model selects real graph tool, creates structured revision; acceptance creates a plan version; restart recovers it |

## Suggested checkpoint

2–3 focused engineering hours, subject to environment and credential readiness.
First resolve database/client connectivity, then ingestion, graph closure, change
impact, agent action and restart. Time recorded should distinguish setup from behavior.

At the checkpoint, record passed/failed cases and the failure cause. If some cases are
incomplete, identify whether scope reduction, implementation correction or a pivot is
the best use of remaining time. Do not call a heuristic scheduling failure a proof
that no feasible schedule exists.

## Exit conditions

- Core graph tool proves a consequential exception/dependency.
- Shared-work compatibility is inspectable.
- Exact selective impact works for a one-fact mutation.
- Live source integration is genuine.
- At least one complete, persisted agent action is working.
- Unsupported and untested capability claims remain explicitly excluded.

This is the build quality bar, not a scoring rubric assigned by the judges.

