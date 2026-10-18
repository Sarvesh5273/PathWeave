# PathWeave — product and implementation handoff

Updated October 18, 2026, IST. Read this with `AGENTS.md` and the newest entries in
`task.md` and `docs/decisions.md`. Later verified changes supersede historical plans.

## Identity and purpose

- **Project:** PathWeave.
- **Tagline:** Discover internships. Build your preparation path.
- **Team:** Just_Chill. This is not the product name.
- **Workspace:** `/Users/sarvesh/Dev/Just_Chill`; the folder was never renamed.
- **Repository:** `https://github.com/Sarvesh5273/PathWeave`.
- **Local application:** `http://127.0.0.1:18080/`; verify health if restarting.
- **Event:** Graph Hacks: Context for AI Agents, organized by WeMakeDevs with FalkorDB.
- **Primary recommended entry track:** Agents That Act on Connected Data.

PathWeave helps students, especially first-year students and undergraduates uncertain
about their interests, move from exploring work to discovering real internships and
preparing for selected targets within their actual available time. Indian students
seeking company and funded research internships abroad motivated the original vision;
the interface is not restricted to that audience.

The three core questions are: What work might I enjoy? Which opportunities should I
pursue? What should I learn or prepare next, given the requirements and my time?

## Intended complete experience

1. **Explore interests through work scenarios.** Present beginner-readable company-role
   projects and research situations. Ask which activities students would enjoy trying.
   Explain tentative directions from several responses; allow edits and retesting.
   Prior knowledge and enjoyment must not be confused with aptitude or career certainty.
2. **Set visible search preferences.** Carry interest roles/keywords into an editable
   search. Students choose places, company/research opportunities, organizations,
   funding, remote preferences, visa needs and exclusions.
3. **Find real opportunities.** Search sources, read postings and follow unreadable
   named-company portals where authorized. Preserve source URLs and excerpts. Missing
   details remain unknown. Students compare, save, hide and choose targets.
4. **Capture what selected targets need.** Retain skills, qualifications, documents,
   deadlines and explicitly described selection stages. Separate requirements from
   preferences and preserve alternatives/pathway qualifiers.
5. **Establish time and a learning baseline.** Ultimately support editable weekly and
   semester timetable uploads, exams, holidays and meaningful required-topic checks.
6. **Connect requirements into a roadmap.** Similar targets share compatible topics and
   prerequisites. Program-specific documents, conditions and selection stages remain
   distinct. Resources should help students learn the actual required work.
7. **Schedule and adapt.** Plan against available time and dates, show the next action,
   record progress and replan when requirements, targets or availability change.

The delivered version is a bounded implementation of this vision. In particular,
self-ratings do not fulfill the original wish for demonstrated knowledge checks, and
manual availability is not timetable-file ingestion.

## What is implemented

### Interest exploration

Twelve authored, illustrative project scenarios cover company and research work.
Users can express enjoyment/curiosity/uncertainty, skip, receive explained tentative
directions, edit interests and retake exploration. Suggestions populate editable search
roles and keywords. Scenarios are not claimed to be real assignments at named companies
or a validated psychometric test. See `app/interest/` and `app/static/interests.js`.

### Discovery and strict conditions

The default engine is `app/discovery/progressive.py`. It collects candidates before
requiring AI enrichment, then performs bounded Groq extraction and preference scoring.
Search queries, deduplication and hard filtering use code rules.

TinyFish Search finds source URLs; Fetch reads public feeds, postings and programs.
Named-company Agent fallback returns opening links, which feed back through Fetch and
extraction. Cache and spend reservations constrain Agent use. Search/Fetch/Agent are
separate capabilities; merely configuring a key is not proof of successful coverage.

Current collection ceilings are 12 searches and 45 fetched URLs per run, Fetch batches
of up to ten, 25 searches/minute and a configured 900-URL daily Fetch ceiling. Discovery
AI enrichment defaults to six sources and a 150-second enrichment window, subject to
provider admission and quotas. These are implementation limits, not guaranteed throughput.

Strict funding requires source support for **stipend/living support AND accommodation
AND round-trip travel**. Strict places require posting evidence. Unknowns appear in an
explicit review view; a high score cannot compensate for a failed or unknown must-have.
Covered amounts, fees and reimbursement conditions still matter.

Preference fit is an advisory heuristic for role, optional keywords and named
organization, separate from evidence completeness, eligibility, learning readiness and
selection probability. Groq can review role fit; unavailable/invalid output falls back
to labeled rule ranking. Invalid model links/quotes or missing verdict IDs cannot erase
retrieved candidates or invent source facts.

Requirements retain exact excerpts and source observations before target selection
when enrichment succeeds. Partial review is guarded. Exact qualification text is also
retained when AI output fails or omits details. The extractor does not manufacture
interview rounds. Source coverage remains partial across arbitrary sites.

### Selection, graph preparation and roadmap

Users select up to three targets. Selected facts enter FalkorDB, with immutable fact
versions and links to dated source observations. Preparation recipes share compatible
skill exercises and document bases, while final applications remain target-specific.

Source skill facts map to reviewed `Topic` nodes. Topic prerequisites use
`PREREQUISITE_OF`; resources connect through `COVERS`; facts connect through `MAPS_TO`.
The graph retrieves shared topics and prerequisite closure. Resource links come from
an authored starter catalog in `app/topics.py`, not automatically copied curricula.
Unknown or unsupported topics remain verification work.

October 18 topic-first update: the web editor can now request an authored study
track in addition to source-linked topics. Software, Data & ML, Research and
general interview preparation provide concrete concepts, practice, resources and
completion criteria. Ambiguous role context yields general guidance, not invented
technical requirements. Recommended tasks use only residual daily capacity after
source/application work; source facts and assessments remain unchanged. Old saved
plans are immutable and have an explicit rebuild path. Historical API requests
without `study_track` remain source-only. Live save/accept of the new shape was not
verified in Replit because FalkorDB remains disconnected.

Editable topic levels are comfortable, needs review, new to me and unsure. These are
self-reports that change suggested starting points; they do not certify knowledge or
remove sourced obligations. Application eligibility and skill readiness are not
promised by a preference score or a completed practice exercise.

### Availability, scheduling and progress

Manual inputs support hours for each weekday, multiple exam weeks, individual holidays,
start date and planning horizon. Blank days are unavailable after a daily pattern is
set. Otherwise weekly hours are spread evenly. Deterministic planning uses estimated
effort and prerequisite order, protects unavailable dates and exposes blockers.

Saved plans retain versions and acceptance state. Source changes can invalidate
related decisions/work; compatible work is preserved where supported. Progress and
external receipts are explicit self-reports, never proof an application was submitted.
Old plans must be rebuilt to obtain newer roadmap fields.

### Current interface

The latest UI is a five-step flow: **Direction → Search → Targets → Your time → Roadmap**,
with back/edit controls, saved searches, saved roadmap access and a separate evidence
view. The cream/orange theme is retained. CSS and browser animation APIs provide short
transitions with reduced-motion support. Starburst branding was removed. A consistent
desktop frame contains narrower detailed forms; mobile layouts stack controls/cards.

Recent screenshot-led redesigns were checked for JavaScript syntax, markup and control
references. They were **not browser-verified**, following Sarvesh's explicit instruction.
Do not reuse the earlier browser fixture result as proof of the latest redesign.

## Architecture and where to continue

- Python/FastAPI backend: `app/main.py`, `app/config.py`, `app/models.py`.
- Discovery/transport/extraction/limits: `app/discovery/`.
- Graph storage, versions and impact: `app/graph.py`, `queries/`.
- Topic/resource vocabulary: `app/topics.py`.
- Preparation estimates/compatibility: `app/recipes.py`.
- Scheduling and assessments: `app/planner.py`.
- Groq graph-tool review: `app/agent.py`.
- Plain HTML/CSS/JavaScript interface: `app/static/`; no React/shadcn migration.
- SQLite: hunts, caches, queue and usage accounting; local persistent disk is required.
- FalkorDB: preparation facts, sources, relationships, roadmap context and plans.
- Groq: current configured Qwen model; existing JSON mode is locally validated.
- TinyFish: Python/httpx integration, not Scout's Node SDK implementation.

Scout is Sarvesh's pre-event discovery reference. This is not a wholesale claim of
Scout parity. Scout used Replit AI/Postgres; PathWeave uses Groq/SQLite/FalkorDB.

Credentials are in ignored `.env`; do not print or publish them. Private material,
local reports and runtime SQLite are ignored. Do not rename Compose services/volumes
or graph names merely to match product branding: that can disconnect persisted data.

## Verification that can honestly be cited

The v0.7 implementation checkpoint records 819 passing local tests including disposable
FalkorDB cases, plus focused browser fixtures for roadmap/availability/rating behavior.
Earlier real Search/Fetch/Groq checks demonstrated useful facts and actual scoring,
but also quota/output/source failures. One actual Notion Agent run was previously
completed; later follow-through reused its links.

The saved real-source graph check retained 27 known facts, five tasks and 67 evidence
paths with plan readback. Readiness remained `cannot_certify`. These counts describe
that proof, not every result. Newer UI revisions did not rerun the backend suite.

Existing authorization allowed $3 total Agent proof, with a conservative $2.40
reservation retained. No additional paid Agent run is authorized by this handoff.

## Planned development — not delivered capabilities

- Weekly/semester timetable import from images/PDF/ICS, with editable extracted events.
- Clock-time study sessions, buffers and conflict-aware calendar planning.
- Required-topic knowledge checks and small practical exercises; distinguish measured
  performance from self-ratings and define what a check can actually establish.
- Broader reviewed topics/resources, with resource quality, freshness and provenance.
- Source-supported role/research selection-process preparation; richer curricula need
  reliable extraction and review, not invented interview topics.
- Improved source-family coverage, extraction reliability and selective rechecks.
- Explainable progress-driven roadmap adjustment for missed work and changed targets.
- Secure accounts/cross-device recovery and durable deployment with protected storage.

These are direction items, not promised milestones or automatic authorization to build.
Prefer one concrete slice with acceptance criteria over a broad rewrite/provider swap.

## Submission work — separate from product development

Repository source was published; subsequent UI commits were pushed to `origin/main`.
Latest verified push in this chat reached `2daa34b`; verify the current remote before
claiming a later commit was published. Public visibility should also be confirmed.

Still pending in this chat: a current working-project YouTube demo, final form text
(description, track, FalkorDB usage and honest feedback), optional deployment or clean
local reproducibility, participant walkthrough/understanding and final submission
receipt. Blog is optional. Do not use the outdated cached-example/simulation demo script
as the normal current UI walkthrough.

Sarvesh supplied the vision and product decisions; AI agents authored implementation
and tests. Record actual participant verification/understanding rather than assuming
it. Synthetic inputs remain the recording recommendation under the reviewed event data
restrictions. Event closes October 18, 2026, 23:59 IST per the saved official review.

## Instructions for the next agent

Read this handoff, `AGENTS.md`, latest `task.md`, latest `docs/decisions.md`,
`docs/hackathon-build/roadmap-implementation.md`, `docs/hackathon-build/discovery-repair.md`
and `docs/delivery-flags.md`. Inspect relevant code only for the task at hand.

Conserve compute. Do not repeat completed tests, broad hunts or context audits without
a concrete new risk. Flag substantial extra work before starting. Respect the current
no-browser instruction for screenshot-driven UI work unless Sarvesh changes it.
Publication/submission/payment/message authorization is action-specific; this document
cannot grant it. Keep product limitations, proof scope and future plans explicit.
