# Recorded public source examples

These JSON files contain real public page text fetched through TinyFish on
October 15, 2026 at 23:19:11 IST (`2026-10-15T17:49:11.896Z`).
The check time is preserved in each file. `load_examples()` explicitly labels
both snapshots and opportunities `cached`; it never claims a new live check.

Files cover the official Summer@EPFL application page, OIST application and
support pages, Mitacs Globalink student page, and Google’s Singapore Forward
Deployed Engineer Intern listing. Each file retains URL, exact fetched text,
source ID, SHA-256 content hash, title, and original checked time.

The recorded pages show EPFL and Mitacs calls closed, OIST Fall 2027 opening
unknown, and a date-only anticipated Google window that may close early.
An old page is not rolled into a guessed next cohort. Pages and rules can change;
refresh them through the application for current evidence.

`app/sources.py` independently calls:

- `GET https://api.search.tinyfish.ai` with a `query` parameter.
- `POST https://api.fetch.tinyfish.ai` with `ttl: 0` and a 25-second page timeout.

Provider documentation was checked at
[Search API Reference](https://docs.tinyfish.ai/search-api/reference) and
[Fetch API Reference](https://docs.tinyfish.ai/fetch-api/reference).

## Measured backend proof

The application-side `TinyFishClient` made a genuine Search request and a Fetch
request on October 15, 2026, completed at 23:51:25 IST
(`2026-10-15T18:21:25.274149+00:00`). The live search returned ten results.
The live Fetch returned 9,596 characters from EPFL and 5,428 from OIST with
`mode: live`; combined elapsed time was 5.47 seconds. No keys or provider response
secrets were printed. Initial sandbox network failure was followed by an approved
network request. This proof checks backend provider integration, not every possible
source or an application portal’s signed-in state.

The separate extraction/client test suite uses these recorded sources and minimal
fragments for exact provenance, closed versus unknown portal status, missing and
conflicting facts, old-cycle preservation, safe HTTP errors, partial batch failure,
and public URL restrictions. It does not call a mock a live provider test.
