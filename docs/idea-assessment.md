# Internship idea assessment

Updated: October 15, 2026, 20:57 IST.
Status: initial assessment preserved. Sarvesh subsequently accepted the narrowed
direction; independent-review.md adds criticism and scope.md contains the revised demo.
Implementation has not started.

## Verdict

[Likely] **KEEP the internship domain; CHANGE the hackathon scope.**
The complete proposed flow is too broad for the remaining event window.
Its strongest differentiator is a graph-backed preparation plan across selected targets,
with evidence-backed eligibility and revisions when requirements change.

No source establishes that this idea will win or that a new idea would improve our odds.
Do not preserve the idea merely because Sarvesh suggested it; evaluate actual proof.

## What is already solid

[Certain] Sarvesh specified user selection of targets, shared weekly capacity,
exam protection, distinct Research/Company views, explicit unknowns, no guaranteed
selection, and a distinction between funding and zero expense.
These are product requirements from the user, not validated adoption evidence.

[Likely] The relationship problem is concrete: one preparation task can support several
targets, but deadlines, prerequisite chains and program exceptions differ.
A source correction can invalidate several eligibility assessments and plans.
These relationships should be traversed in FalkorDB.

## Main weaknesses

1. [Likely] Broad discovery, a taste test, filtering, readiness interviews, two-track
   roadmaps and detailed scheduling together create too much build and verification work.
2. [Certain] Matching quizzes, job discovery and application tracking already appear
   in Simplify's first-party product pages. Those features alone do not establish novelty.
   This is a bounded comparison, not an exhaustive competitor audit.
   Sources: [Pathway](https://simplify.jobs/pathway),
   [tracker](https://simplify.jobs/job-application-tracker).
3. [Certain] No validation evidence has been supplied for the taste test.
   Source-grounded questions can introduce work areas; they do not prove aptitude
   or predict internship suitability. Keep editable interests for the MVP.
4. [Likely] If FalkorDB only stores listings and an LLM writes a calendar, the graph
   contributes too little. The graph should resolve requirements, reusable preparation
   and change dependencies; a deterministic scheduler should allocate time.
5. [Likely] Readiness hours are estimates, institutional documents have waiting time,
   and external deadlines can be rolling or uncertain. A precise calendar is not proof
   of achievable readiness. Expose estimate ranges and assumptions.

## What live sources revealed

Sources below were fetched on October 15, 2026. These examples assess the product
requirements; they are not internship recommendations or eligibility advice.

### Opposite document requirements

[Certain] EPFL's application FAQ lists CV, transcripts and motivation letter, and
explicitly says recommendation letters are not needed or considered; uploading them
may harm the application.
[Certain] Mitacs' application FAQ requires at least one professor reference letter.
A shared generic application checklist would be wrong.
Sources: [EPFL](https://summer.epfl.ch/apply.html),
[Mitacs](https://www.mitacs.ca/our-programs/globalink-research-internship-students/).

[Likely] Share a CV foundation or research summary when compatible, but retain
program-specific final documents, formats and prohibited/irrelevant submissions.
Merge by an explicit compatibility rule and identity, not similar names.

### Cycle and source status

[Certain] Mitacs' page says Summer 2027 applications have concluded.
The TinyFish extraction of EPFL says applications are closed with a next deadline
of November 29, 2026 at 23:39 AOE; another web extractor omitted that date block.
Do not turn a future deadline into an assertion that applications are open.
Verify the precise source fragment during ingestion.

### Employer conditions

[Certain] A Google Singapore 2027 listing describes a paid internship and prioritizes
applicants with existing Singapore work rights who do not require visa sponsorship.
It states an anticipated October 13–November 15, 2026 application window that may
close early when projects fill.
[Likely] Therefore paid status is not proof of travel funding or visa support,
and the latest listed date is not a guaranteed application window.
Source: [Google listing](https://www.google.com/about/careers/applications/jobs/results/115691171337904838-forward-deployed-engineer-intern-2027?location=Singapore).
The source does not establish that a particular Indian student qualifies.

## Comparison with two possible pivots

This is our design judgment, not a market ranking or a claim of originality.

| Candidate | Graph proof | Main cost/risk | Current judgment |
| --- | --- | --- | --- |
| Narrow internship preparation agent | Shared prerequisites, application exceptions, source-change impact | Reliable extraction and explicit uncertainty | [Likely] Best current choice; user has supplied substantial domain thinking |
| Recall-response agent for a synthetic supply chain | Lot → component → product → shipment traversal determines recall scope | New domain assumptions and convincing validated scenarios | [Likely] Strong fallback if internship core fails its spike |
| Correction-aware shared agent memory | A changed fact invalidates dependent decisions across agent handoffs | Adjacent memory tools already exist; more abstract demo | [Likely] Fits Track 02, but requires a clearer new workflow |

[Likely] Switching ideas solely for novelty is not justified by current evidence.
A short implementation spike should decide whether the internship graph delivers a
convincing result. Pivot if it fails, rather than adding graph-themed UI.

## Recommended scope and track

Primary track recommendation: **Agents That Act on Connected Data**.
Secondary memory track is optional only if meaningful persisted context and an agent
handoff actually work. Research/Company are user-facing preparation categories;
they are not the hackathon's tracks. This product is not Company Brain just because
some internships are at companies.

Proposed MVP: public-source discovery → explicit target selection → evidence-backed
requirements → shared preparation graph → one weekly plan → explained revision.
See docs/hackathon-build/scope.md for the concrete proposal.

## Go / pivot spike

After the product direction is accepted:

1. Ingest one permitted official source with grounded fields and explicit unknowns.
2. Build a tiny graph for three illustrative targets with one shared preparation task,
   two distinct final documents, and an exam blackout.
3. Traverse task prerequisites and program-specific exceptions in FalkorDB.
4. Change one synthetic source fact, traverse the affected plan dependencies,
   and produce a correct schedule revision with an evidence path.
5. Compare output with fixed expected cases; show useful behavior beyond listing search.

Target about three focused engineering hours, an estimate rather than a guarantee.
If the graph behavior cannot be shown, reduce requirements further or consider the
recall-response fallback. Do not sink the whole event into ingestion or onboarding.

## Unresolved product decisions

- Accept narrow MVP or choose a pivot.
- Update: narrow direction accepted; independent review recommends revise/conditional-go.
- Whether funded research is the lead demo and Company is a secondary view.
- Keep genuine TinyFish search/fetch in the running app; a fixture is only a clearly
  labeled reproducibility fallback, not a substitute for the user's live discovery goal.
- API credentials for deployed TinyFish and Groq are not yet provided/verified.
- Synthetic applicant scenarios for the hackathon until the personal-data rule is clarified.

