# Cream grid interface — October 16, 2026

Sarvesh authorized a frontend usability/design pass and suggested cream, a grid-based
feel and shades of orange. This changes presentation/navigation, not the discovery
engine, FalkorDB schema, budgets or provider authorization. No frontend-specific skill
is installed; existing HTML/JavaScript and Playwright checks are the implementation path.

## Visual system

- Cream graph-paper background: `#f7f1e6`; content paper: `#fffaf2`.
- Burnt-orange primary: `#b4481e`; darker orange for text: `#893414`.
- Peach supporting surfaces: `#f4ddc6`; dark warm ink: `#352e25`.
- Subtle 64px paper grid, bordered tiles, compact status labels and generous spacing.
- Existing DM Sans/Space Grotesk; italic Georgia accent in the main headline.
- Static connected-preparation diagram, not a fake graph screenshot or fabricated data.
- New `app/static/site.css` owns the design. Original `style.css` is retained, no
  longer linked by the updated page; do not delete unfamiliar/user changes casually.

## User journey

1. Two entry paths: known interests → focused search; unsure → optional activity cards.
   Exploration starts editable preferences; no career/aptitude scores or classification.
2. Roles/location first, company/research choices visible. Organizations, visa, funding,
   keywords/exclusions and other preferences remain available under a collapsed section.
3. Actual run-event stages (Search, Read, Extract, Rank); queued/partial/failed states
   remain explicit. Detailed source activity is available separately. No invented
   progress percentage or claim that skipped stages completed.
4. Shortlist grid: source/read date, unconfirmed openings/visa, funding limits and
   advisory-fit disclaimer. Evidence expands; save/hide and selection are separate.
5. Select targets, then Continue to preparation. Hours/exam settings live on the
   preparation page, not next to the initial discovery form. Existing actual plan
   building/acceptance/receipt/simulation behavior is retained.
6. Preparation review explicitly names Groq and distinguishes it from TinyFish's
   browser Agent. The latter's disabled/enabled configuration comes from health data;
   no UI change enables or claims live verification of that feature.
7. Evidence page carries actual paths/fragments, plus source refresh controls.

## Verification and boundaries

Use `scripts/check_discovery_ui.py` for mocked-response frontend regressions and
screenshots. It covers keyboard entry, exploration/skip, advanced preferences, actual-
event partial/failed rendering, selection before time entry, saved/hidden views, hunt
reload, Agent-off disclosure, and 390px/320px overflow checks. This is not provider proof.

`scripts/check_discovery_live_ui.py` exercises actual API/FalkorDB with separately
retrieved live data on a dedicated verification server/graph; it makes no new provider
calls and must not overwrite the main preparation workspace. Record actual results in
../verification.md and build-notes.md. No need to rerun unrelated backend suites for
static frontend changes. Main saved plans and provider/spending gates must stay intact.

Responsive baseline: two-column result tiles plus selected-target rail on wide desktop;
single column on phones. Semantic labels, focus outlines, skip link, pressed-selection
states and collapsible native details support keyboard navigation. This is not an
exhaustive accessibility certification or all-device guarantee.

Public deployment/publication/submission and recurring/metered provider work still
retain their earlier separate authorization gates; "full auth" in this UI discussion
does not create a submission receipt or establish Sarvesh's technical understanding.

### Recorded outcome

Both targeted browser gates passed. Mocked discovery checks verify the entry/exploration/
advanced-search/run-status/listing interaction flows. Actual isolated API/FalkorDB using
previously retrieved data verifies planning, shared/category work views, evidence,
acceptance/reload and mobile layout. No new provider calls or main workspace changes.
JavaScript syntax and diff whitespace checks passed. The test server was stopped;
main app remains at port 18080. User design feedback is still to be collected.
