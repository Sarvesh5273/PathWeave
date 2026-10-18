import json

import pytest

from app.discovery.contracts import WebPage
from app.discovery.feeds import MAX_FEED_ROWS, parse_feed
from app.discovery.urls import MAX_SOURCE_LEADS, canonical_url, classify_url, detect_ats, posting_links
from app.models import SourceSnapshot


UUID = "12345678-1234-1234-1234-123456789abc"


def page(url, *, requested=None, text="", links=None, body=None):
    return WebPage(snapshot=SourceSnapshot(id="test-source", url=url, text=text),
                   requested_url=requested or url, links=links or [], json_body=body)


@pytest.mark.parametrize("url", [
    "http://localhost/jobs/123", "http://127.0.0.1/jobs/123", "http://127.1/jobs/123",
    "http://0x7f000001/jobs/123", "http://10.0.0.1/jobs/123", "http://[::1]/jobs/123",
    "https://metadata.google.internal/", "https://example.test/jobs/123",
    "https://user:password@example.com/jobs/123", "https://example.com:8080/jobs/123",
    "https://example.com/login", "https://example.com/%6cogin", "https://example.com/%256cogin",
    "https://example.com/signin.html", "https://example.com/candidates/jane",
    "https://example.com/jobs/123?token=secret", "https://example.com/jobs/123?api_key=secret",
    "https://example.com/jobs/123?session_id=private", "https://example.com/jobs/123?email=jane%40example.com",
    "https://example.com/jobs/123?tok%2565n=secret", "https://example.com/jobs/123?utm_source=jane%2540example.com",
    "https://example.com/jobs/123?utm_source=%00private",
    "https://example.com/jobs/123?next=https%3A%2F%2Flocalhost",
    "https://example.com/jobs/123?utm_source=jane%40example.com",
    "https://example.com/jobs/123#token=secret", "https://example.com/jobs/123?jobid=a%2Fb",
    "https://example.com/jobs/123?jobid=123&jobid=456", "https://sub.linkedin.com/jobs/123",
    "https://indeed.com/viewjob?id=123", "https://example.com\\@localhost/jobs/123",
    "https://example.com/jobs/123\n", "file:///jobs/123", "mailto:jobs@example.com",
])
def test_canonical_rejects_private_and_excluded_inputs(url):
    assert canonical_url(url) is None
    assert classify_url(url) is None


def test_generic_canonical_identity_and_safe_params():
    assert canonical_url("http://WWW.Example.com:80/jobs/123/?utm_source=web&JobID=123#apply") == "https://example.com/jobs/123?jobid=123"
    assert canonical_url("https://example.com/?q=engineering") == "https://example.com/"
    assert canonical_url("https://notlinkedin.com/jobs/123") == "https://notlinkedin.com/jobs/123"
    assert canonical_url("https://example.com/jobs?req=abc-123&id=456") == "https://example.com/jobs?id=456&req=abc-123"
    assert canonical_url("https://8.8.8.8/jobs/123") == "https://8.8.8.8/jobs/123"


@pytest.mark.parametrize("url,ats,posting,readable", [
    ("https://boards.greenhouse.io/ACME/jobs/123?utm_source=web", "greenhouse", True, True),
    ("https://boards.eu.greenhouse.io/acme", "greenhouse", False, True),
    ("https://job-boards.greenhouse.io/acme?gh_jid=123", "greenhouse", True, True),
    (f"https://jobs.lever.co/ACME/{UUID}/apply", "lever", True, True),
    ("https://jobs.eu.lever.co/acme", "lever", False, True),
    (f"https://jobs.ashbyhq.com/Acme/{UUID}", "ashby", True, False),
    ("https://jobs.ashbyhq.com/Acme%20Labs", "ashby", False, False),
    ("https://acme.wd5.myworkdayjobs.com/en-US/External/job/New-York/Software-Intern_R123", "workday", True, True),
    ("https://acme.wd5.myworkdayjobs.com/External", "workday", False, True),
    ("https://jobs.smartrecruiters.com/Acme/123456789-engineering-intern", "smartrecruiters", True, True),
    ("https://careers.smartrecruiters.com/Acme", "smartrecruiters", False, True),
    ("https://apply.workable.com/ACME/j/abc123/", "workable", True, True),
    ("https://apply.workable.com/acme", "workable", False, True),
])
def test_ats_variants(url, ats, posting, readable):
    ref = detect_ats(url)
    assert ref.ats == ats
    assert bool(ref.posting_url) is posting
    assert ref.readable is readable
    assert ref.organization
    lead = classify_url(url)
    assert lead.kind == ("posting" if posting else "board")
    assert lead.url == (ref.posting_url or ref.board_url)
    assert canonical_url(lead.url) == lead.url


def test_greenhouse_embed_keeps_secret_guard():
    assert detect_ats("https://boards.greenhouse.io/embed/job_app?for=acme&token=123") is None
    assert canonical_url("https://boards.greenhouse.io/embed?for=acme") == "https://job-boards.greenhouse.io/acme"


@pytest.mark.parametrize("url", [
    "https://jobs.lever.co/", "https://jobs.lever.co/acme/login", "https://jobs.lever.co.evil.com/acme",
    "https://apply.workable.com/api/v1/widget/accounts/acme", "https://jobs.ashbyhq.com/..",
])
def test_ats_invalid_or_nonboard(url):
    assert detect_ats(url) is None


@pytest.mark.parametrize("path", ["/", "/careers", "/jobs", "/jobs/search", "/jobs/engineering", "/internships", "/programs/summer-research"])
def test_generic_index_not_a_posting(path):
    assert classify_url("https://example.com" + path).kind == "page"


@pytest.mark.parametrize("path", ["/jobs/123456", "/careers/job/engineering-intern-123456", "/job/software-engineer-intern", "/jobs?job_id=123456"])
def test_clear_generic_posting_url(path):
    assert classify_url("https://example.com" + path).kind == "posting"


def test_posting_links_relative_markup_dedupe_and_source_redirect():
    source = "https://careers.acme.co.uk/jobs"
    result = posting_links(page(source, requested="https://acme.co.uk/careers", links=[
        "/jobs/123456?utm_source=site", "/jobs/123456#apply", "https://acme.co.uk/programs/summer-research",
        "https://other.co.uk/jobs/123456", "https://evil.com/jobs/123456",
        "https://job-boards.greenhouse.io/acme/jobs/777", "/login?next=/jobs/123456",
        "https://indeed.com/jobs/123456", "/jobs/image.png", "#apply",
    ], text='<a href="/jobs/456789">Research Intern</a>\n[Summer role](/jobs/987654)'))
    assert len(result) == 5
    assert all(lead.source_url == source and lead.via == "link" for lead in result)
    assert result[0].kind == "posting"
    assert next(lead for lead in result if lead.url.endswith("456789")).title == "Research Intern"
    assert next(lead for lead in result if "summer-research" in lead.url).kind == "page"


@pytest.mark.parametrize("final", ["http://localhost/jobs", "https://example.com/login", "https://example.com/jobs?session=x", "https://linkedin.com/jobs"])
def test_posting_links_reject_unsafe_redirect(final):
    assert posting_links(page(final, requested="https://example.com/jobs", links=["https://jobs.lever.co/acme"])) == []


def test_workday_title_location_and_ashby_board_leads():
    board = "https://acme.wd5.myworkdayjobs.com/External"
    leads = posting_links(page(board, links=[
        "/en-US/External/job/New-York/Software-Engineer-Intern_R1234", "/External/job/New-York/Software-Engineer-Intern_R1234",
        f"https://jobs.ashbyhq.com/Acme/{UUID}", "/External/search",
    ]))
    workday = next(lead for lead in leads if "myworkdayjobs" in lead.url)
    assert workday.title == "Software Engineer Intern"
    assert workday.location == "New York"
    assert sum(lead.kind == "posting" for lead in leads) == 2


def test_link_collection_bounded_and_login_wall_skipped():
    assert len(posting_links(page("https://example.com/jobs", links=[f"/jobs/{i + 1000}" for i in range(2000)]))) == MAX_SOURCE_LEADS
    assert posting_links(page("https://example.com/jobs", text="Please sign in to view the jobs", links=["/jobs/123456"])) == []


def test_greenhouse_feed_safe_ids_and_metadata():
    ref = detect_ats("https://boards.greenhouse.io/acme")
    leads = parse_feed(ref, page(ref.feed_url, body={"jobs": [
        {"id": 123, "title": "<b>Software Intern</b><script>private()</script>", "location": {"name": "Remote"}, "company_name": "Acme Inc", "absolute_url": "http://localhost/private"},
        {"id": "123", "title": "duplicate"}, {"id": "../login", "title": "bad id"},
        {"id": True, "title": "boolean"}, {"id": 456, "title": "jane@example.com"},
    ]}))
    assert len(leads) == 1
    assert leads[0].url == "https://job-boards.greenhouse.io/acme/jobs/123"
    assert leads[0].title == "Software Intern"
    assert leads[0].location == "Remote"
    assert leads[0].organization == "Acme Inc"
    assert leads[0].via == "feed" and leads[0].source_url == ref.feed_url


def test_lever_feed_preserves_safe_public_posting_only():
    ref = detect_ats("https://jobs.eu.lever.co/acme")
    rows = [{"text": "Research Intern", "hostedUrl": f"https://jobs.eu.lever.co/acme/{UUID}?utm_source=feed", "categories": {"allLocations": ["London", "Remote", None]}, "descriptionPlain": "Requirements remain for root extraction."}]
    rows += [{"text": "bad", "hostedUrl": value} for value in [
        f"https://jobs.eu.lever.co/acme/{UUID}?auth=x", f"https://jobs.eu.lever.co/other/{UUID}",
        "https://jobs.eu.lever.co/acme", "http://localhost/jobs/123", "https://example.com/jobs/123456",
    ]]
    leads = parse_feed(ref, page(ref.feed_url, body=rows))
    assert len(leads) == 1
    assert leads[0].location == "London; Remote"
    assert leads[0].organization == "Acme"


def test_smartrecruiters_feed():
    ref = detect_ats("https://careers.smartrecruiters.com/Acme")
    leads = parse_feed(ref, page(ref.feed_url, body={"content": [
        {"id": "123456789", "name": "AI Intern", "location": {"city": "Paris", "country": "France"}, "company": {"name": "Acme Labs"}},
        {"id": "../../login", "name": "bad"}, {"id": 987654321, "name": "Data Intern", "location": {"fullLocation": "Remote Europe"}},
    ]}))
    assert len(leads) == 2
    assert leads[0].url == "https://jobs.smartrecruiters.com/Acme/123456789"
    assert leads[0].location == "Paris, France"
    assert leads[0].organization == "Acme Labs"
    assert leads[1].location == "Remote Europe"


def test_workable_feed_shortcode_and_safe_url_fallback():
    ref = detect_ats("https://apply.workable.com/acme")
    leads = parse_feed(ref, page(ref.feed_url, body={"name": "Acme Robotics", "jobs": [
        {"title": "Robot Intern", "shortcode": "abc123", "city": "Berlin", "country": "Germany"},
        {"title": "Data Intern", "url": "https://apply.workable.com/acme/j/DEF456"},
        {"title": "bad", "shortcode": "../login"}, {"title": "bad", "url": "https://apply.workable.com/acme"},
        {"title": "bad", "url": "https://apply.workable.com/acme/j/ABC123?token=secret"},
    ]}))
    assert len(leads) == 2
    assert leads[0].url == "https://apply.workable.com/acme/j/ABC123"
    assert leads[0].organization == "Acme Robotics"
    assert leads[0].location == "Berlin, Germany"


@pytest.mark.parametrize("board,data", [
    ("https://job-boards.greenhouse.io/acme", {"jobs": []}),
    ("https://jobs.lever.co/acme", []),
    ("https://careers.smartrecruiters.com/acme", {"content": []}),
    ("https://apply.workable.com/acme", {"jobs": []}),
])
def test_empty_feed_is_not_failure(board, data):
    ref = detect_ats(board)
    assert parse_feed(ref, page(ref.feed_url, body=data)) == []
    assert parse_feed(ref, page(ref.feed_url, body={"error": "no jobs"})) is None


@pytest.mark.parametrize("final", [
    "https://boards-api.greenhouse.io/v1/boards/other/jobs", "https://example.com/jobs",
    "https://boards-api.greenhouse.io/login", "http://localhost/jobs",
    "https://boards-api.greenhouse.io/v1/boards/acme/jobs?token=secret",
])
def test_feed_redirect_must_preserve_public_board_identity(final):
    ref = detect_ats("https://boards.greenhouse.io/acme")
    assert parse_feed(ref, page(final, requested=ref.feed_url, body={"jobs": [{"id": 123, "title": "Intern"}]})) is None


def test_json_text_repairs_and_limits():
    ref = detect_ats("https://boards.greenhouse.io/acme")
    text = '```json\n{"jobs": [{"id": 123, "title": "Engineering\nIntern", "absolute\\_url": "ignored"}]}\n```'
    assert parse_feed(ref, page(ref.feed_url, text=text))[0].title == "Engineering Intern"
    assert parse_feed(ref, page(ref.feed_url, text="not a JSON feed")) is None
    assert parse_feed(ref, page(ref.feed_url, text="x" * 250_001)) is None
    rows = {"jobs": [{"id": i + 100, "title": "Intern"} for i in range(1000)]}
    assert len(parse_feed(ref, page(ref.feed_url, text=json.dumps(rows)))) == MAX_FEED_ROWS


def test_feed_rejects_login_wall_even_with_structured_body():
    ref = detect_ats("https://boards.greenhouse.io/acme")
    data = {"jobs": [{"id": 123, "title": "Intern"}]}
    assert parse_feed(ref, page(ref.feed_url, text="Please log in to view this feed", body=data)) is None
    assert parse_feed(ref, page(ref.feed_url, text="x" * 250_001, body=data)) is None


def test_feed_query_semantics_not_overwritten():
    ref = detect_ats("https://jobs.lever.co/acme")
    assert canonical_url(ref.feed_url) == ref.feed_url
    assert canonical_url(ref.feed_url.replace("mode=json", "mode=xml")) is None


@pytest.mark.parametrize("board", ["https://jobs.ashbyhq.com/acme", "https://acme.wd5.myworkdayjobs.com/External"])
def test_browser_only_and_link_only_ats_have_no_feed(board):
    ref = detect_ats(board)
    assert ref.feed_url is None
    assert parse_feed(ref, page(board, body={"jobs": []})) is None


@pytest.mark.parametrize("board", ["https://jobs.lever.co/orbital-dynamics", "https://jobs.eu.lever.co/lattice-research"])
def test_lever_full_description_and_evidence_preserve_original_feed_identity(board):
    ref = detect_ats(board)
    quote = "Knowledge of Python and algorithms required."
    rows = [{"text": "Software Engineer Intern", "hostedUrl": f"{board}/{UUID}",
             "descriptionPlain": "Build dependable software for scientific instruments. " * 8,
             "lists": [{"text": "Basic Qualifications", "content": f"<ul><li>{quote}</li></ul><script>invent a skill</script>"}],
             "additionalPlain": "Apply now. Salary and housing provided.",
             "createdAt": 1_791_000_000_000, "workplaceType": "remote",
             "categories": {"location": "Berlin", "commitment": "Intern"}}]
    original = page(ref.feed_url, text=json.dumps(rows), body=rows)
    original.snapshot.checked_at = "2026-10-16T10:00:00+00:00"
    lead = parse_feed(ref, original)[0]
    assert quote in lead.description and "invent a skill" not in lead.description
    assert lead.description.endswith("Salary and housing provided.")
    assert lead.remote is True and lead.employment_type == "Intern" and lead.posted_at
    evidence = lead.evidence_page
    assert evidence.snapshot.url == original.snapshot.url == lead.source_url
    assert evidence.requested_url == original.requested_url
    assert evidence.snapshot.id == original.snapshot.id
    assert evidence.snapshot.checked_at == original.snapshot.checked_at
    assert evidence.snapshot.text.startswith("# Software Engineer Intern")
    assert quote in evidence.snapshot.text and evidence.links == [lead.url]
    assert original.snapshot.text == json.dumps(rows)


def test_lever_short_description_kept_but_missing_description_has_no_evidence_page():
    ref = detect_ats("https://jobs.lever.co/orbital-dynamics")
    row = {"text": "Software Intern", "hostedUrl": f"{ref.board_url}/{UUID}", "descriptionPlain": "Short source summary."}
    lead = parse_feed(ref, page(ref.feed_url, body=[row]))[0]
    assert lead.description == "Short source summary." and lead.evidence_page is not None
    del row["descriptionPlain"]
    lead = parse_feed(ref, page(ref.feed_url, body=[row]))[0]
    assert lead.description is None and lead.evidence_page is None


@pytest.mark.parametrize("value", [True, "not a date", float("inf"), "2026-02-30"])
def test_feed_bad_date_does_not_drop_safe_sibling_metadata(value):
    ref = detect_ats("https://job-boards.greenhouse.io/orbital-dynamics")
    lead = parse_feed(ref, page(ref.feed_url, body={"jobs": [{"id": 12345, "title": "Software Intern", "first_published": value}]}))[0]
    assert lead.posted_at is None


@pytest.mark.parametrize("path", ["/j/3EE3968348", "/j/3ee3968348/", "/j/3EE3968348/apply"])
def test_workable_unscoped_posting_not_company_board(path):
    url = "https://apply.workable.com" + path
    ref = detect_ats(url)
    assert ref.ats == "workable" and ref.org == "" and ref.feed_url is None
    assert ref.organization == "Unknown" and ref.posting_id == "3EE3968348"
    assert canonical_url(url) == "https://apply.workable.com/j/3EE3968348"
    assert classify_url(url).kind == "posting"


@pytest.mark.parametrize("slug,company", [("rapyuta-robotics", "Rapyuta Robotics"), ("lattice-research", "Lattice Research")])
def test_real_shaped_workable_escaped_markdown_feed_preserves_unscoped_posting(slug, company):
    ref = detect_ats(f"https://apply.workable.com/{slug}")
    text = r'''```json
{"name": "COMPANY", "description": "Robotics research
Build useful software", "jobs": [{"title": "Software Engineer Intern", "shortcode": "3EE3968348",
"employment\_type": "Intern", "url": "https://apply.workable.com/j/3EE3968348",
"shortlink": "https://apply.workable.com/j/3EE3968348",
"application\_url": "https://apply.workable.com/j/3EE3968348/apply",
"published\_on": "2025-10-15", "country": "Japan", "city": "Koto City"}]}
```'''.replace("COMPANY", company)
    leads = parse_feed(ref, page(ref.feed_url, text=text))
    assert len(leads) == 1 and leads[0].url == "https://apply.workable.com/j/3EE3968348"
    assert leads[0].organization == company and leads[0].source_url == ref.feed_url
    assert leads[0].employment_type == "Intern" and leads[0].posted_at == "2025-10-15"
    assert leads[0].location == "Koto City, Japan"


@pytest.mark.parametrize("url,shortcode", [("https://apply.workable.com/j/OTHER123", "3EE3968348"),
    ("https://apply.workable.com/other/j/3EE3968348", "3EE3968348"),
    ("https://apply.workable.com/j/3EE3968348?token=private", "3EE3968348"),
    ("https://apply.workable.com/j/3EE3968348", None),
    ("https://apply.workable.com/j/3EE3968348", True)])
def test_workable_unscoped_link_requires_matching_feed_shortcode_and_safe_identity(url, shortcode):
    ref = detect_ats("https://apply.workable.com/rapyuta-robotics")
    row = {"title": "Software Intern", "url": url, "shortcode": shortcode}
    assert parse_feed(ref, page(ref.feed_url, body={"name": "Rapyuta Robotics", "jobs": [row]})) == []
