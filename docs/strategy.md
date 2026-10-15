# Strategy and dated plan

Status: provisional planning framework. Sarvesh's internship idea is assessed;
narrowed MVP scope is proposed in docs/hackathon-build/scope.md.

## What we optimize

[Likely] A narrow, original, verifiable agent workflow is our strongest use of the
remaining time. Breadth across all tracks is useful only after the core workflow works.
A win remains uncertain; no source establishes our odds.

## Idea evaluation

Codex will give a **keep / change / reject** verdict, identify the largest weakness
first, and suggest a concrete alternative where needed. Evaluate:

| Dimension | Internal weight | Evidence needed |
| --- | --- | --- |
| Necessary graph work | 30% | A connected constraint or multi-hop path determines the action |
| User value | 20% | Defined user, painful task, useful finished outcome |
| Originality | 20% | Clear contribution beyond sponsor tutorials and libraries |
| Feasibility | 15% | Can implement and verify within the available days |
| Demo clarity | 15% | One scenario proves the advantage quickly |

These weights are OUR heuristic, not published judging criteria.
Confidence in competitor novelty is limited by research coverage.

Reject or rework ideas that mainly display a graph, answer generic document questions,
wrap an existing memory server, require restricted personal data, or need several
unproven integrations before any meaningful result can appear.

## Demo contract to decide before code

- One user task with a surprising relationship that matters.
- One actual agent tool selection and FalkorDB query.
- One evidence path/source record displayed beside the decision.
- One domain action (explicitly simulated if not real).
- One graph change that changes the decision for a known reason.
- One missing-evidence case.
- Persistence/agent handoff only where required by our chosen track or claimed feature.

This contract prevents claiming capabilities we cannot show.

## Execution targets — all IST

| Date | Target | Exit evidence |
| --- | --- | --- |
| Oct 15 evening | Assess idea; pick primary track; write scope and key graph questions | Approved direction, graph sketch, decisive demo case |
| Oct 16 | Prove graph queries, then complete seed → query → agent → outcome | One usable end-to-end workflow |
| Oct 17 | Implement changed-context behavior, evidence UI and required memory/coordination; begin deployment | Repeatable demo, fresh-process persistence where claimed |
| Oct 18 by 14:00 | Feature freeze | Required features verified; cut everything optional |
| Oct 18, 14:00–18:00 | Fresh setup check, README, demo video and exact submission fields | Reviewable complete package |
| Oct 18 by 20:00 | Internal submission target, after user authorization | Official submission receipt |
| Oct 18, 20:00–23:59 | Contingency buffer | Resolve upload/platform issues; edits only if officially allowed |

Official deadline: Oct 18, 23:59 IST. Internal targets are recommendations.
Sarvesh has said availability is sufficient; do not assume uninterrupted 24-hour work.

## Responsibilities

- Sarvesh: domain idea, product judgment, useful cases, meaningful contribution,
  actual verification, understanding and final submission authorization.
- Codex: technical decisions, graph model, architecture, implementation, tests,
  evidence review, documentation and submission preparation.
- Research agents: bounded primary-source research when useful; coordinate before
  editing shared files.

## Scope controls

One primary persona, one workflow, one data pipeline, one graph, 4–6 domain tools.
Start from synthetic data where it can honestly represent the use case.
Cap time spent on integration spikes; retain a working path at every milestone.
Use GraphRAG SDK only if document extraction is essential. Blog, extra tracks,
complex animations and additional connectors follow a ready core submission.

