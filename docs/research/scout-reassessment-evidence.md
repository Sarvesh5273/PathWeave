# October 16 reassessment — Scout + preparation

Scope: bounded read-only product review requested by Sarvesh after testing concerns.
No rebuild, deployment, paid browser run, publication or submission authorized here.

## User report versus observed evidence

- Sarvesh reports the current app is not working, appears to have no TinyFish search,
  and feels like a hardcoded internship list rather than Scout plus preparation.
  His exact failing query, browser error and steps are not yet supplied.
- [Certain] The original vision in user-idea.md explicitly includes real TinyFish
  discovery and Scout-like preferences. Those goals were not abandoned by narrowing.
- Historical 133 passing tests prove the recorded cases, not broad discovery quality
  or Sarvesh's current browser experience.

## Fresh bounded runtime probe

Executed DiscoverService.discover directly using current project settings; no graph
writes, saved-plan changes or application endpoint mutations. Limit: two result URLs.

- Query: `software engineering internship Germany 2027 official careers`.
- Runtime: 4.00 seconds; returned mode `live`, provider `TinyFish`.
- Amazon source checked at 2026-10-16T10:28:46.104633+00:00
  (October 16, approximately 15:58 IST); fetched text length 7,191 characters.
- Returned `2027 Software Dev Engineer Intern - Germany`, source ID
  `source-86b2c1fe97f6ba64`, verification `partial`, cycle `unknown`.
- **Zero known structured facts.** All 24 current fact fields were unknown,
  including degree levels, fields, funding and application deadline.
- Indeed result failed with `bot_blocked`; Amazon source outcome was labeled
  `success` even though its structured extraction remained wholly unknown.
- [Certain] This proves fresh discovery beyond cached programs exists. It also
  demonstrates that generic retrieval is not useful general preparation extraction.
- [Certain] A separate TinyFish Fetch of the Amazon page shows explicit basic
  qualifications: STEM degree; a general-purpose programming language; CS fundamentals
  including algorithms, data structures and complexity. It also states a remaining
  academic term after internship, salary and relocation support. No deadline or visa
  sponsorship should be inferred from those facts.
- [Unknown] This does not reproduce the user's exact browser failure or establish
  that every current query works. No API key value was printed.

Source: https://www.amazon.jobs/en/jobs/10554701/2027-software-dev-engineer-intern-germany

## Scout public-page inspection

TinyFish Fetch read the home page, `/how-it-works`, `/hunts/new`, and GitHub repository.
The public repository was shallow-cloned into an approved temporary directory for
independent source review; dependencies were not installed and its code was not run.

- Public flow advertises roles, places, visa/funding preferences, live Search/Fetch,
  AI structured extraction, ranking, deduplication and optional browser fallback.
- `/how-it-works` reports activity "since 7 Oct 2026": 439 searches, 1,981 pages,
  301 tracked listings and 39 completed runs; browser runs are reported as zero.
  These are **site-reported counters**, not independently verified executions.
- No hunt was created. Page copy and source inspection are not proof of working
  end-to-end Scout discovery today.
- The reviewed Git snapshot is `0fbad8cc71f92849e5a9a90ee2dc30e5496f12eb`, authored
  and committed October 13, 2026, 12:51:04 UTC (18:21 IST), subject
  "Scout: find jobs and internships abroad". Git timestamps corroborate the public
  page's pre-event history; they are not an independent audit of all authorship.
- [Certain] The reviewed Scout snapshot predates the event start according to its
  recorded commit date. Provenance must be distinguished from newly implemented
  hackathon work. Reusing its main finder unchanged is not automatically approved
  just because participants own the repository.

Sources:
- https://scout-careers.replit.app/
- https://scout-careers.replit.app/how-it-works
- https://scout-careers.replit.app/hunts/new
- https://github.com/Sarvesh5273/Scout

## Official rules and deployment facts rechecked

TinyFish Search followed by Fetch read official rules, resource links, plans and free
tier docs. All statements describe the published pages, not an actual deployed account.

- [Certain] Docker, self-hosted FalkorDB and FalkorDB Cloud are all explicitly accepted.
  Cloud is not mandatory. Local reproducibility plus a working demo video is permitted;
  live deployment remains preferred.
- [Certain] Main coding/design must begin after the event starts, original event work
  is judged, and general libraries/templates/infrastructure may be reused. The review
  cannot certify that wholesale reuse of a pre-existing product is eligible.
- [Certain] Free Cloud docs list 100 MB RAM/dataset; no TLS, persistence or backups;
  unused instances stop after one day and are deleted after seven days. Startup lists
  $73/month, TLS and periodic backups but no continuous persistence.
- [Likely] A durable Docker host with private DB networking and HTTPS for the web API
  is a valid alternative. No free host or protected managed endpoint has been proven.
- Closing deadline rechecked: October 18, 2026, 23:59 IST. Internal 20:00 target remains
  a recommendation, not an organizer deadline.
- User's newly pasted panel again reports Oct 17, 01:03 IST opening and a team lock.
  This is user-provided evidence, not signed-in independent verification; preserve
  the conflicting public schedule rather than pretending the discrepancy is settled.
- No new numeric rubric, demo duration or win probability was established.

Sources:
- https://www.wemakedevs.org/hackathons/falkordb/rules
- https://www.wemakedevs.org/hackathons/falkordb/resources
- https://docs.falkordb.com/cloud/tiers/free
- https://www.falkordb.com/plans/

The resources page text extraction succeeds but omits link labels. Its outbound links
include getting-started, Docker, Cloud, Browser, Cypher, clients, algorithms, integrations,
community projects, the organizer tutorial, two direct videos and two playlists.
Missing link labels in extracted prose do not imply the website has no resources.

## Implementation follow-up: TinyFish cost boundary

On October 16, after Sarvesh authorized $3 total metered proof, free Search/Fetch
rechecked official pricing and run controls:

- https://www.tinyfish.ai/pricing lists $0.016 per Agent step, Search/Fetch free;
  Agent default concurrency two. Contract/legacy rates may differ by account.
- https://docs.tinyfish.ai/key-concepts/runs says custom `agent_config.max_steps`
  is beta/account-gated, accepts 1–500, and default is 150 if omitted. A duration
  limit is not the documented hard step cap.
- No account hard-cap activation was verified. The new transport sends a configured
  max_steps only behind a verified-cap flag, and never retries 403 without it.
  Root keeps the live path disabled rather than making an uncapped metered request.
- No top-up, subscription, organizer/support message or metered run occurred.
