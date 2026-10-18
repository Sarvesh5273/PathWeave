from dataclasses import replace
import hashlib

import pytest

from app.config import settings
from app.discovery.basic import BasicDiscoveryEngine,source_listing
from app.discovery.basic import source_locations
from app.discovery.contracts import DiscoveryPreferences,SourceLead,WebPage
from app.discovery.state import DiscoveryState
from app.models import SourceSnapshot


URL="https://company.example/jobs/1001/software-engineer-intern"


def page(url=URL,title="Software Engineer Intern",text=None,links=None,json_body=None):
    text=text or f"# {title}\nLocation: Tokyo, Japan\nExperience with Python is required. Submit your application online."
    return WebPage(snapshot=SourceSnapshot(id="source-test",url=url,title=title,text=text,
        content_hash=hashlib.sha256(text.encode()).hexdigest()),requested_url=url,links=links or [],json_body=json_body)


class Web:
    def __init__(self,pages,leads):self.pages={p.requested_url:p for p in pages};self.leads=leads;self.fetches=[]
    def search(self,task):return self.leads
    def fetch(self,urls,**kwargs):
        self.fetches.extend(urls)
        return [self.pages[u] for u in urls if u in self.pages],{u:"Fixture Fetch unavailable" for u in urls if u not in self.pages}


def runner(tmp_path,web,monkeypatch):
    monkeypatch.setattr("app.discovery.ai.structured_call",lambda *args,**kwargs:pytest.fail("Basic finder made an AI request"))
    config=replace(settings,groq_key="configured-but-not-used",tinyfish_agent_enabled=False,discovery_basic_seconds=30)
    return BasicDiscoveryEngine(config,DiscoveryState(str(tmp_path/"state.sqlite")),web=web)


def test_basic_search_and_filters_work_with_no_ai_and_unknown_requirements(tmp_path,monkeypatch):
    lead=SourceLead(url=URL,title="Software Engineer Intern",snippet="Internship in Tokyo, Japan")
    progress=[]
    result=runner(tmp_path,Web([page()],[lead]),monkeypatch).run(DiscoveryPreferences(roles=["software engineer"],locations=["Japan"],opportunity_types=["company_roles"]),on_progress=lambda value:progress.append(value))
    assert result.listings and result.listings[0].locations
    assert result.listings[0].requirements==[]
    assert result.listings[0].visa_status=="unknown" and result.listings[0].funding_level=="unknown"
    assert result.usage["ai_attempts"]==result.usage["extractions"]==0
    assert any(p.listings for p in progress)


def test_failed_posting_fetch_retains_search_lead_with_unknown_location(tmp_path,monkeypatch):
    lead=SourceLead(url=URL,title="Software Engineer Intern",snippet="Search says Tokyo, Japan")
    result=runner(tmp_path,Web([],[lead]),monkeypatch).run(DiscoveryPreferences(roles=["software engineer"],opportunity_types=["company_roles"]))
    assert result.listings and result.partial
    assert result.listings[0].verification=="uncertain"
    assert result.listings[0].locations==[]  # Search snippet is not a verified posting location.


def test_actual_feed_title_and_location_filter_without_posting_ai(tmp_path,monkeypatch):
    board="https://job-boards.greenhouse.io/example"
    feed="https://boards-api.greenhouse.io/v1/boards/example/jobs"
    p=page(feed,title="",json_body={"jobs":[{"id":1001,"title":"Software Engineer Intern","location":{"name":"Tokyo, Japan"}},{"id":1002,"title":"Marketing Intern","location":{"name":"Japan"}}]})
    result=runner(tmp_path,Web([p],[SourceLead(url=board,title="Example Careers")]),monkeypatch).run(DiscoveryPreferences(roles=["software engineer"],locations=["Japan"],opportunity_types=["company_roles"]))
    assert any(v.title=="Software Engineer Intern" and v.locations==["Tokyo, Japan"] for v in result.listings)
    assert result.usage["ai_attempts"]==0


@pytest.mark.parametrize("title",["Careers","Careers at Intrinsic","Search for Jobs","Internships","Software Engineering Internships","Internships Abroad","Top 10 internships"])
def test_generic_index_is_not_a_specific_listing(title):
    assert source_listing(SourceLead(url="https://company.example/careers",title=title,kind="page"),page("https://company.example/careers",title=title)) is None


def test_later_unknown_details_do_not_become_ready_claims():
    p=page(text="# Software Engineer Intern\nLocation: Tokyo, Japan\nVisa sponsorship is available. Salary and housing covered. Python required.")
    listing=source_listing(SourceLead(url=URL,title=p.snapshot.title,kind="posting"),p)
    assert listing.visa_status=="unknown" and listing.funding_level=="paid"
    assert listing.stipend is True and listing.housing is True and listing.round_trip_travel is None
    assert listing.call_status=="unknown" and listing.requirements==[]


def test_explicit_country_labels_do_not_require_a_country_alias_or_city():
    assert "Japan" in source_locations("[2027 Internships] Japan")
    assert "Canada" in source_locations("Research internship in Canada")
    assert source_locations("International internship; location not stated")==[]


def test_explicit_unknown_city_is_not_replaced_with_company_office_geography():
    p=page(text="# Software Engineer Intern\nLocation: Tallinn\nCompany offices also include Tokyo, Japan.\nPython required.")
    listing=source_listing(SourceLead(url=URL,title=p.snapshot.title,kind="posting"),p)
    assert listing.locations==["Tallinn"]


def test_deadline_closure_without_emptying_saved_history(tmp_path,monkeypatch):
    p=page(text="# Software Engineer Intern\nLocation: Tokyo, Japan\nThis position is closed and no longer accepting applications.")
    result=runner(tmp_path,Web([p],[SourceLead(url=URL,title=p.snapshot.title)]),monkeypatch).run(DiscoveryPreferences(roles=["software engineer"],opportunity_types=["company_roles"]))
    assert result.listings[0].call_status=="closed"


def test_internship_filter_does_not_admit_senior_fulltime_feed_jobs(tmp_path,monkeypatch):
    board="https://job-boards.greenhouse.io/example"
    feed="https://boards-api.greenhouse.io/v1/boards/example/jobs"
    p=page(feed,title="",json_body={"jobs":[{"id":1001,"title":"Senior Software Engineer","location":{"name":"Tokyo, Japan"}},{"id":1002,"title":"Software Engineer Intern","location":{"name":"Tokyo, Japan"}}]})
    result=runner(tmp_path,Web([p],[SourceLead(url=board,title="Careers")]),monkeypatch).run(DiscoveryPreferences(roles=["software engineer"],locations=["Japan"],opportunity_types=["company_roles"]))
    assert all("Senior" not in v.title for v in result.listings)
    assert any(v.title=="Software Engineer Intern" for v in result.listings)
