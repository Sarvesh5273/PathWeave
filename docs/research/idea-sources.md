# Idea assessment sources

Read October 15, 2026. All findings are bounded by extraction coverage.
These are product-research examples, not opportunities recommended to the user.

## Directly read first-party sources

- [Summer@EPFL overview](https://summer.epfl.ch/).
- [EPFL application FAQ](https://summer.epfl.ch/apply.html).
- [Mitacs Globalink students](https://www.mitacs.ca/our-programs/globalink-research-internship-students/).
- [CERN overview](https://home.web.cern.ch/summer-student-programme/): generic opening
  text did not identify the year clearly; not used to establish a current opportunity.
- [Google Singapore listing](https://www.google.com/about/careers/applications/jobs/results/115691171337904838-forward-deployed-engineer-intern-2027?location=Singapore).
- [Simplify Pathway](https://simplify.jobs/pathway).
- [Simplify tracker](https://simplify.jobs/job-application-tracker).
- [TinyFish documentation](https://docs.tinyfish.ai/).
- [TinyFish Search reference](https://docs.tinyfish.ai/search-api/reference).
- [TinyFish Fetch reference](https://docs.tinyfish.ai/fetch-api/reference).

## Runtime integration findings

[Certain] TinyFish has public Search and Fetch APIs, both requiring X-API-Key.
Search is GET api.search.tinyfish.ai; Fetch is POST api.fetch.tinyfish.ai.
Free daily allowances and throttling exist; exact implementation needs provider error
handling. A connection available to Codex does not automatically provide deployment
credentials. No credential file was read or secret printed during this assessment.

## Extraction limits

The public EPFL date block appeared in TinyFish extraction but not in another web
extractor. Preserve the checked fragment before using dates; do not silently infer
the next cycle, application opening or a timezone conversion.
Some Mitacs institution links include older cycle years despite 2027 headings.
Institution eligibility requires validating the actual referenced current list.
Google's listing describes prioritization of existing work rights; do not convert
“prioritized” into an invented universal ban or sponsorship guarantee.

## Comparisons and alternatives

The Simplify overlap is based only on matching, discovery, preferences and tracking
documented on its own pages. We did not establish whether it implements the proposed
cross-target preparation or source-change graph behavior.
Recall-response and correction-aware memory are candidate designs, not market-validated
alternatives or claims of uniqueness.

One read-only Codex agent reviewed graph modeling and planning risks. No application
was run, no database query was tested, and no internship application was performed.

