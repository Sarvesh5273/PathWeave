# Project Scope — draft for review

Updated: October 15, 2026, 22:10 IST.
Status: **DIRECTION ACCEPTED** by Sarvesh; independent review completed with a
revise/conditional-go verdict. Demo and quality criteria below incorporate that review.
Implementation now exists; see ../verification.md for measured results.
Original idea: docs/research/user-idea.md.
Assessment: docs/idea-assessment.md.

## Project Name Candidates

Working descriptor: Internship preparation agent.
Final product name is pending; do not spend build time on naming.

## One-Line Summary

An agent that catches incompatible internship requirements and external application
blockers, then repairs the affected preparation plan while preserving usable work.

## Target User

Indian undergraduates exploring funded international research and paid company
internships. Use a clearly synthetic applicant in the hackathon demonstration.
No real CV, grades, personal identifiers or documents enter the graph.

## Problem

Targets share some preparation but differ in eligibility, required documents,
funding, deadlines and selection stages. Planning each separately duplicates effort;
merging everything can miss exceptions. A change can make yesterday's plan invalid.

## Core Workflow

1. Enter editable interests and small search preferences.
2. Run bounded TinyFish Search/Fetch over public official opportunity sources.
3. Review source-linked cards; distinguish open, closed, future and unknown calls.
4. Explicitly select up to three targets for the first MVP.
5. Review typed eligibility conditions and document checklists.
6. Supply or load synthetic availability, exam blackout and readiness inputs.
7. Agent retrieves compatible shared work and prerequisites from FalkorDB.
8. Deterministic scheduling creates one plan with Research/Company views.
9. Refresh a source or alter scenario availability; the graph finds affected
   conclusions and tasks, and the agent proposes an explained revision.
10. User accepts the revision; persist the selected targets and plan version.

## What We Are Building

- Bounded genuine public-source discovery in the application.
- Simple editable interests; search/compare/select flow.
- Source URL, checked time, cycle and explicit missing fields on opportunity cards.
- Explicit minimum versus preferred criteria; met/not met/unknown criteria outcomes.
- Editable readiness self-report labeled accurately; untested skills remain
  Not assessed. Readiness quizzes are deferred from the core build.
- Program-specific deliverable checklist and compatible reusable foundations.
- FalkorDB task-dependency and fact-level source-impact traversals.
- Explicit external waiting states such as recommendation receipt, separate from
  preparation effort and call-opening status.
- One shared weekly budget; configurable exam blackout.
- Proposed outcomes: feasible under stated estimates, at risk, infeasible, cannot
  certify. Do not treat a heuristic failure as proof of global infeasibility.
- Explainable next action, source trace, before/after revision and saved plan.
- Reproducible synthetic scenario alongside clearly labeled live/cached results.

## What We Are Not Building in This MVP

- General 10–12-question taste test, readiness quizzes or validated aptitude classification.
- Exhaustive global opportunity coverage and complete visa eligibility advice.
- Universal autonomous extraction with silently accepted contradictory fields.
- Automatic application submission, emails or contact with recruiters.
- Full interview simulator or fabricated selection stages.
- Real personal-document ingestion.
- Independent time budgets for Research and Company.
- Guaranteed optimal schedule, selection probability or guaranteed funding coverage.

These are scope cuts, not claims that Sarvesh has abandoned the long-term vision.

## Graph Model Sketch

Entities: Opportunity, FactVersion, Criterion, SourceVersion, Deliverable, PrepTask,
Artifact, Assessment, PlanVersion. Use the smallest useful schema in the spike.

Relationships:
- Opportunity → HAS_CRITERION → Criterion → USES_FACT → FactVersion
- Opportunity → REQUIRES / DOES_NOT_ACCEPT → Deliverable → USES_FACT → FactVersion
- FactVersion → SUPPORTED_BY → SourceVersion
- PrepTask → SUPPORTS → Deliverable
- PrepTask → DEPENDS_ON → PrepTask
- PrepTask → PRODUCES → Artifact → SUPPORTS → Deliverable
- Assessment → FOR → Opportunity; Assessment → USED → FactVersion
- PlanVersion → INCLUDES → PrepTask; PlanVersion → USED → FactVersion

Fact identity is scoped to program, cohort and applicability. Preserve the source
fragment and distinguish official facts from planner estimates/prerequisite assumptions.
Nonsemantic refreshes do not invalidate decisions. A changed fact invalidates only its
dependent conclusions; source retrieval/extraction failure creates uncertainty.

Exact schema and queries belong in the implementation spec after acceptance.
Public facts and synthetic scenario state can persist. Real applicant profile stays
out of the graph; actual permitted production handling requires a separate decision.

## Agent and Scheduler Roles

The agent chooses bounded tools, resolves requirements, retrieves shared work,
explains affected targets and proposes changes.
FalkorDB supplies the connected requirements/prerequisite/evidence graph.
Deterministic code handles time allocation, precedence and capacity.

Each prep task has estimated effort and optional elapsed waiting time. Deadlines retain
source timezone and certainty; a user's target date is separate. Rolling-close windows
are flagged. Unknown deadline/effort means the plan cannot certify completion.

## Demo Path — revised after independent review

Lead with two real program sources and a clearly synthetic applicant. Preserve real
call states; use future preparation, not a claim that both portals currently accept
applications. Any compressed dates or altered policy are explicitly simulated.

1. Application backend performs genuine public-source discovery/fetch.
2. Select EPFL and OIST for preparation; show cycle and checked source fragments.
3. Graph queries find shared base preparation, distinct final statements, EPFL's
   no-reference exception and OIST's recommendation-receipt dependency.
4. Show a useful next action and a waiting state. A requested letter is not a received
   letter; a future deadline is not proof of an open portal. Do not contact anyone.
5. Allocate preparation under one estimated-hours budget with protected exam weeks.
6. Apply one labeled simulated change to a specific OIST requirement. Graph traversal
   finds only dependent conclusions/tasks; show exact paths and proposed changes.
7. Preserve the unrelated target and compatible completed base preparation.
8. Accept the revision and restart; recover plan version and evidence history.

OIST's sourced statement limits and application fee can provide additional small
checks; support does not imply zero fees. Keep these checks bounded.

The earlier 6-hour shared foundation plus two separate 2-hour statements remains a
small correctness fixture (10 hours versus duplicated 16), not the headline demo.
No hours-saved or real student-outcome claim is validated.

## Inspiration And References

- Original user vision in docs/research/user-idea.md.
- Official EPFL and Mitacs document requirements; Google listing as a rolling-window
  and work-authorization example. Links and limits are in the assessment.
- Sponsor's bounded graph tools/evidence approach; original decision workflow is ours.

## Submission Story

Two lead targets, one preparation budget, incompatible requirements and an external
blocker. Show the graph-returned exception, action proposal and selective decision
repair; preserve completed work. Up to three selections can follow the core proof.
Primary hackathon track recommendation: Agents That Act on Connected Data.

## Time Budget and Build Gate

User says availability is sufficient; exact working hours remain unspecified.
Event closes October 18, 23:59 IST; internal submission target remains 20:00 IST.
Independent review complete; see ../independent-review.md and proof-gate.md.
Next: encode these behaviors in acceptance criteria and implement a bounded terminal/API
spike before full interface work. The 2–3 hour checkpoint is a planning estimate,
not a tested implementation duration or an automatic pivot deadline.

## Open Choices

Final name; supported live sources and degree/domain scope; backend credential
connection. Narrow direction is already accepted; readiness quizzes are deferred.

