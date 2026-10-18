# Graph Hacks: verified event review

Reviewed: October 15, 2026, approximately 19:54 IST.
Confidence: [Certain] means directly observed source evidence; [Likely] means a recommendation
or interpretation; [Guessing] means a gap. “Certain” does not certify future page changes.

October 16 follow-up: official rules and resource links were fetched again during a
user-requested Scout/product reassessment. The requirements below remain consistent
with that extraction. Docker/self-hosted use is explicitly accepted; managed Cloud
is not compulsory. A pre-event Scout finder must not be presented as new event work
without distinguishing provenance and checking any ambiguous reuse. No new rubric
or signed-in submission state was established. See research/scout-reassessment-evidence.md.

## 1. Who runs it and what is mandatory

[Certain] Event: **Graph Hacks: Context for AI Agents**. WeMakeDevs organizes it in
collaboration with **FalkorDB**, the named sponsor/technology partner. It is free, online,
and open worldwide, with solo participation or teams of up to four people. Each person
can belong to one team. Registration, team management and submission are on WeMakeDevs,
according to the FAQ. No additional sponsor is named on the pages reviewed.
Sources: [overview](https://www.wemakedevs.org/hackathons/falkordb),
[rules](https://www.wemakedevs.org/hackathons/falkordb/rules).

[Certain] This is an open-ended challenge within three tracks. No single fixed problem
or compulsory dataset is assigned. We must choose a task where connected data changes
an agent's decisions or actions. FalkorDB must be the primary graph database and central
to the product. A visualization over another database is insufficient.
Sources: [challenge](https://www.wemakedevs.org/hackathons/falkordb#challenge),
[rules](https://www.wemakedevs.org/hackathons/falkordb/rules).

[Likely] Practical acceptance check: remove FalkorDB and the submitted workflow loses
its relationship reasoning, shared memory or company context. Change a relevant edge,
rerun the same task, and demonstrate the changed outcome. This shows the actual graph
is used; it is not a claim that no other database could theoretically implement the task.

## 2. Exact timing and discrepancy

| Item | Observed evidence | Status |
| --- | --- | --- |
| Hacking begins | October 15, 2026, 00:01 IST | [Certain] Rules and schedule |
| Submission closes | October 18, 2026, 23:59 IST | [Certain] Rules, schedule and FAQ agree |
| Submission opens, public schedule | October 15, 2026, 00:01 IST | [Certain] Public text |
| Submission opens, user team panel | October 17, 2026, 01:03 IST | User-provided observation; not independently checked |
| Team lock | Team cannot change after submitting | User-provided panel text; verify before first submission |
| Judging/results dates | Not found | Unresolved |

The official event window spans almost four days (95 hours 58 minutes), October 15–18.
The pasted “3 days, 4 hours” countdown describes remaining time at the capture,
not the total event length. At the start of this review (about 19:30 IST on October 15),
roughly 76.5 hours remained. Countdown values must be recalculated when needed.
Source: [schedule](https://www.wemakedevs.org/hackathons/falkordb/schedule).

[Certain] The schedule also says registration is the only current checkpoint while
another paragraph says submissions open with hacking. Public extraction left the
registration panel at “Loading”; it cannot establish the account-specific opening time.
**The opening time is unresolved.** Build now, keep a submission package ready, and
check the signed-in panel or organizer clarification.
[Likely] Aim to submit by October 18, 20:00 IST to preserve almost four hours of buffer.

## 3. Tracks and advertised prizes

| Track | Focus in the official brief | Advertised prize |
| --- | --- | --- |
| Agents That Act on Connected Data | Multi-hop reasoning, graph queries/algorithms as tools, MCP selection, graph-driven action, explanations | iPhone 18 Pro |
| Agent Memory and Coordination | Persistent episodic/semantic/procedural memory, history, agent handoffs, shared reads/writes, user/tenant separation | PS5 with GTA VI |
| Company Brain | Connected docs/tickets/chats, people/teams/projects, ownership, decision provenance and updates | M6 Mac Mini |

[Certain] Rules and FAQ permit entering any or all three and require naming every entered
track. The organizer tutorial instead describes a single-track entry. Prefer the rules
and verify the actual form. [Likely] Choose one primary track first; add another only if
the working demo proves its requirements.
Sources: [tracks/prizes](https://www.wemakedevs.org/hackathons/falkordb#tracks),
[rules](https://www.wemakedevs.org/hackathons/falkordb/rules),
[organizer tutorial](https://www.wemakedevs.org/blogs/how-to-build-an-agent-that-reasons-over-a-graph).

[Certain] The advertised pool is **$20,000 worth of prizes**, principally the listed
hardware, rather than a stated $20,000 cash award. The overview adds an AirPods 5 prize
for one best blog post and t-shirts for every member of the top 50 teams. It says every
member of a winning team receives the track prize. These are the organizer's advertised
prize names; this review does not verify product availability or shipping terms.
Platform terms permit prize substitutions.
Sources: [prizes](https://www.wemakedevs.org/hackathons/falkordb#prizes),
[terms, section 8](https://www.wemakedevs.org/terms).

## 4. What judges appear to value

[Certain] The reviewed event pages contain no numeric judging weights, judge roster,
detailed scoring rubric or demo duration limit. Do not invent them.

[Certain] The organizer's October 15 article has a judging-advice section. It emphasizes
demonstrating that the graph changes the agent's behavior, making deeper relationships
visible through evidence paths, and explicitly identifying missing information.
This is organizer guidance, not a formal weighted rubric.
Source: [article](https://www.wemakedevs.org/blogs/how-to-build-an-agent-that-reasons-over-a-graph).

[Likely] Our internal evaluation should emphasize:
a concrete user decision; necessary graph traversal; original work; a complete product
loop; traceable evidence; a reliable live demo; and honest measured outcomes.
The relative weights in strategy.md belong to us, not the judges.

## 5. Required submission package

[Certain] The rules require all of:

- Public source repository.
- README with setup instructions and graph data model.
- The Cypher queries or graph algorithms the product relies on.
- Working project demo video.
- Live deployment, or complete local setup instructions if deployment is not possible.
- Named entry track(s).

The FAQ prefers a live deployment. Local reproducibility plus video remains allowed.
Sources: [rules](https://www.wemakedevs.org/hackathons/falkordb/rules),
[FAQ](https://www.wemakedevs.org/hackathons/falkordb#faq).

[Likely] Include sample data, one-command seeding, tested setup versions, the actual
graph-tool trace, expected outputs, a failure example and reset instructions.
Optional blog entry should explain original work only after core deliverables are ready.

## 6. Rules that affect our design

[Certain] Main coding and design must start after October 15, 00:01 IST. General
libraries, templates, infrastructure, public APIs and open-source assets may be reused;
the main submission/FalkorDB implementation must be new work during the event.
Sources: [rules](https://www.wemakedevs.org/hackathons/falkordb/rules),
[FAQ](https://www.wemakedevs.org/hackathons/falkordb#faq).

[Certain] AI coding tools are allowed, must be disclosed, and participants must understand
and explain the submitted code, graph model, queries, architecture and decisions.
Wholly generated work without meaningful participant contribution, verification or
understanding may be rejected. Codex is a technical collaborator; the participant remains
Sarvesh (and any human teammates). Do not invent a registered team seat for Codex.
Source: [rules](https://www.wemakedevs.org/hackathons/falkordb/rules).

[Certain] Data restrictions are unusually strong: the rule allows public, synthetic or
owned data, but also excludes private, login-protected, paywalled, personal or restricted
information. Ownership does not clearly override those exclusions.
[Likely] Use synthetic people/company/customer records and permitted public nonpersonal
data. A real Slack/Notion/CRM import would need organizer clarification even if owned.
Source: [data rule](https://www.wemakedevs.org/hackathons/falkordb/rules).

[Certain] Team/participant IP remains theirs. Platform terms additionally grant the
organizer and event sponsors a limited license to evaluate/display/showcase a submission.
Platform account use requires age 18 or parental/guardian consent for under-18 users.
Conduct rules prohibit harassment, plagiarism, sabotage and judging manipulation.
Sources: [rules](https://www.wemakedevs.org/hackathons/falkordb/rules),
[terms, sections 2/5/6](https://www.wemakedevs.org/terms),
[conduct](https://www.wemakedevs.org/coc).
No participant eligibility attestation was collected or fabricated in this session.

## 7. Resources and originality risks

[Certain] Official resources include getting-started, Docker/Cloud, Browser, Cypher,
official language clients, algorithms, integrations, GraphRAG SDK, community projects,
an organizer tutorial and four video links/playlists.
Source: [resource hub](https://www.wemakedevs.org/hackathons/falkordb/resources).
The linked videos were inventoried; they were not watched or transcribed.

[Certain] The organizer tutorial already implements **Blast Radius**, a service
dependency/on-call/change investigation agent with graph paths and persistent findings.
Sponsor examples also cover graph chat, persistent memory, code graphs and query generation.
[Likely] A similar idea needs a specific new decision workflow and proof of original work;
renaming a tutorial is insufficient.
Sources: [tutorial](https://www.wemakedevs.org/blogs/how-to-build-an-agent-that-reasons-over-a-graph),
[CodeGraph](https://github.com/FalkorDB/code-graph),
[Graphiti MCP](https://docs.falkordb.com/agentic-memory/graphiti-mcp-server).

## 8. Open questions

1. Actual submission opening time: public schedule versus signed-in team panel.
2. Can submission content/code be edited after first submission, and what gets frozen?
3. Formal rubric, judge names, judging dates and winner announcement date.
4. Demo duration/format, any repository cutoff, and deployment availability expectations.
5. Blog prize submission method/deadline.
6. Interpretation of owned private data and redacted/synthetic company data if needed.
7. Which track choices the real form offers.

[Certain] Official technical/team support is the
[FalkorDB Discord](https://discord.com/invite/Y2mMT9VdMy); WeMakeDevs lists
contact@wemakedevs.org. No message was sent and no recurring monitor was created.

## 9. Skill adaptation

The installed hackathon skills were reviewed: discovery, registration, rules, map,
resources, ideation, scope, PRD, spec, checklist, build, preparation and submission.
Their account/state/tool flow assumes Devpost. This event's FAQ instead specifies
WeMakeDevs. We use the relevant planning principles and documents, and verify this
event against its own official site. Devpost registration/submission gates and
placeholder event data were not applied. No rules-agreement state was invented.
