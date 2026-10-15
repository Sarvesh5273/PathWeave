# Independent review — completed

Reviewer: independent_review, a fresh agent without inherited conversation history.
Requested by Sarvesh on October 15, 2026.
Recorded: October 15, 2026, 22:10 IST.
Status: completed; agent remains listed for reuse.
This is a read-only design and source review. No runtime was validated.

## Verdict

[Likely] **REVISE, then conditionally proceed. Retain the internship domain.**
Shared preparation and source-change propagation are compelling only when they
prevent a consequential mistake and produce a correct, reviewable action.
The original 6 + 2 + 2 hour scenario is too weak as the main demo.

The parent accepts this objection. The accepted narrowed product direction remains
in place; the main proof and acceptance criteria below replace the weaker demo.

## Strongest independent objections

### 1. Graph bookkeeping can be superficial

[Likely] A database outage that breaks the app does not demonstrate meaningful graph
use. Extra labels or hops do not establish useful reasoning.
A real traversal must return a relationship, exception or dependency that changes
the application's proposed action, and the application must consume that result.

Required demonstration: correctly reject wrong document reuse, identify an external
waiting dependency, then repair only the affected decisions.

### 2. Compatibility needs explicit rules

[Certain] EPFL accepts self-translation of transcripts and warns against uploading
recommendation letters. Mitacs requires translated and notarized transcripts when
needed plus a qualifying reference. OIST requires at least one qualifying
recommendation to be received by its system before application submission; applicants
cannot submit those letters directly.

[Likely] Reuse a base academic-record or CV preparation task where compatible.
Keep final deliverables, format limits and submission channels specific to each call.
Similarity of document names or an LLM claim cannot establish compatibility.

Sources: [EPFL](https://summer.epfl.ch/apply.html),
[Mitacs](https://www.mitacs.ca/our-programs/globalink-research-internship-students/),
[OIST](https://www.oist.jp/admissions/research-internship/apply-research-internship).

### 3. Call status must gate the plan

[Certain] Mitacs Summer 2027 applications have concluded. EPFL's current page describes
closed applications and the next November 29, 2026 deadline. OIST Spring 2027's deadline
was October 15, 2026, 23:59 JST, equivalent to October 15, 20:29 IST, already past
when reviewed. OIST lists April 15, 2027 for Fall 2027; its schedule is tentative.

[Likely] Use these as truthful future-preparation or closed-call examples. A future
deadline is not evidence of an open portal. Compressed planning weeks or a policy
change for the demo must be labeled simulated.

Sources: [EPFL](https://summer.epfl.ch/apply.html),
[Mitacs](https://www.mitacs.ca/our-programs/globalink-research-internship-students/),
[OIST schedule](https://www.oist.jp/admissions/research-internship/apply-research-internship).

### 4. Field changes need selective impact

[Likely] A whole-page hash is useful for refresh detection, not sufficient for decision
invalidation. A changed footer must leave semantic facts unchanged.
A changed program requirement should affect the decisions that used that fact.

Minimum design:
- Stable fact identity scoped by program, cohort and applicable country.
- Versioned values supported by source fragments.
- Decision/task dependencies on specific fact versions.
- Missing or contradictory extraction yields an uncertain state.
- Unaffected work and still-compatible completed artifacts remain usable.

### 5. The build is still broad

[Likely] Remove readiness quizzes from the core build. Use editable self-reported
readiness with untested skills marked Not assessed. Keep live discovery short and bounded.
Use two lead planning targets; support up to three selections after the core works.

The application's own TinyFish and LLM credentials remain an integration risk.
Codex's connected research tools do not prove deployment access.

## Real decision cases worth demonstrating

[Certain] OIST's official page also limits its statement to 250 words/1500 characters
and lists a 5,000 JPY application fee. Its support page lists travel, accommodation,
administrative and stipend support. Funding therefore does not imply no application fee.

[Certain] The current Mitacs India block lists citizenship, degree, institution and
grade conditions, including an IIT exclusion for the 2027 cohort.
Google's Singapore listing prioritizes existing work rights; it does not state a
universal hard ban on applicants needing sponsorship.

[Likely] Distinguish hard conditions, preferences, fees, waiting states and source
uncertainty. Use only the small subset required for the demo; these examples are
not permission to build an exhaustive eligibility engine.

Sources: [OIST application](https://www.oist.jp/admissions/research-internship/apply-research-internship),
[OIST support](https://www.oist.jp/admissions/research-internship/program-description),
[Mitacs](https://www.mitacs.ca/our-programs/globalink-research-internship-students/),
[Google listing](https://www.google.com/about/careers/applications/jobs/results/115691171337904838-forward-deployed-engineer-intern-2027?location=Singapore).

## Competitive positioning

[Likely] Strongest story:
“An internship preparation agent catches incompatible requirements and external
blockers, then repairs the affected plan without throwing away completed work.”

Primary hackathon track: Agents That Act on Connected Data.
Research/Company are the product's categories, not event track names.

[Certain] Matching and application tracking overlap with existing Simplify features.
Do not lead with discovery or a quiz as the novelty claim.
Sources: [Simplify](https://simplify.jobs/pathway),
[tracker](https://simplify.jobs/job-application-tracker).

[Likely] A real tool → graph result → proposed revision → accepted, persisted state
loop is necessary. Evidence display and correctness matter more than a sprawling
graph visualization. Adoption and saved-time claims remain unvalidated.

The reviewer inspected one sponsor showcase and one organizer winner recap.
They provide product-completion examples, not this event's scoring rubric:
[sponsor showcase](https://www.falkordb.com/blog/how-builders-at-hack-for-humanity-used-falkordb-to-solve-real-community-problems/),
[organizer recap](https://www.wemakedevs.org/blogs/first-commit-hackathon-recap-and-whats-next).
Neither establishes our winning odds or undisclosed judge preferences.

## Alternative considered

[Likely] A campus-kitchen recall agent has a naturally clear action:
public recall notice → synthetic ingredient lot → meal batches → proposed stock hold.
It needs new domain assumptions and testing work. The reviewer judges that benefit
insufficient to pivot now; retain it as a fallback if the internship graph fails.

The reviewer used an FDA downstream-recall notice as a motivating source:
[FDA notice](https://www.fda.gov/safety/major-product-recalls/2026-recalls-food-products-associated-powdered-milk-california-dairies-inc-due-potential-salmonella).
The parent has not audited this alternative's feasibility. It is not a confirmed
replacement or a product-safety recommendation.

## Minimum competitive demo

1. Real application-side public-source discovery, with cycle, source time and unknowns.
2. EPFL and OIST as future-preparation targets for a synthetic applicant.
3. Shared base preparation plus distinct final statements and program exceptions.
4. OIST recommendation receipt is an external blocker; the next action responds to it.
5. One capacity budget and protected exam weeks.
6. Labeled simulated fact update: show the changed fact, affected paths and revision.
7. Unrelated target and compatible completed base work survive.
8. User accepts the revision; restart and recover plan version and evidence.

Keep the hours arithmetic as a small correctness fixture.

## Engineering gate and kill criteria

Use the concrete cases in [proof-gate.md](hackathon-build/proof-gate.md).
The review suggested a 2–3 hour terminal/API spike before full UI work.

Parent qualification: that duration is a diagnostic checkpoint, not a validated effort
estimate or an automatic pivot deadline. Assess which behavior failed and why.
An unavailable credential is an integration issue; it does not prove the idea is weak.

Revise or pivot if the actual graph contributes only listings; compatibility remains
opaque; a single fact change indiscriminately stales every plan; live discovery cannot
be made real; core cycle/waiting/preference checks still fail; or the full tool-to-action
loop cannot be completed in the remaining build time.

## Research coverage and limits

Independently checked official hackathon overview, rules, schedule, resources and
tutorial; EPFL, Mitacs, OIST and Google sources; Simplify pages; one sponsor showcase
and one organizer winner recap. Repository material was inspected where accessible;
one parking repository returned 404.
Bounded originality review, not exhaustive market research.

The parent independently fetched OIST application/support pages and confirmed the
recommendation receipt rule, fee, statement limits and cycle deadlines.
No application code, FalkorDB instance, LLM call or deployed integration was tested.

