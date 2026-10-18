from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.config import settings
from app.discovery.contracts import DiscoveryListing, DiscoveryPreferences, EngineResult, RunEvent, WebPage
from app.discovery.state import DiscoveryState
from app.graph import GraphStore
from app.models import Fact, SourceSnapshot


TOKEN="testbrowser12345678901234567890"
URL="https://careers.example.org/jobs/1001/software-engineer-intern"


@pytest.fixture
def api(tmp_path,monkeypatch):
    name="just_chill_discovery_api_test_"+uuid4().hex
    graph=GraphStore(replace(settings,db_graph=name))
    assert graph.health()["status"]=="ok"
    ledger=DiscoveryState(str(tmp_path/"discovery.sqlite"))
    monkeypatch.setattr(main,"store",graph)
    monkeypatch.setattr(main,"discovery_state",ledger)
    monkeypatch.setattr(main,"settings",replace(settings,demo_tools_enabled=True))
    try:
        with TestClient(main.app) as client:
            yield client,graph,ledger,monkeypatch
    finally:
        assert name.startswith("just_chill_discovery_api_test_") and name!=settings.db_graph
        db=graph._db()
        if name in db.list_graphs():
            db.select_graph(name).delete()
        db.close()


def seed(ledger):
    hunt=ledger.create_hunt(TOKEN,DiscoveryPreferences(roles=["software engineer"]))
    p=WebPage(snapshot=SourceSnapshot(id="source-test",url=URL,title="Software Engineer Intern",
        text="# Software Engineer Intern\nBasic qualifications: Python and algorithms required."),requested_url=URL)
    listing=DiscoveryListing(id="listing-test",title="Software Engineer Intern",organization="Example",
        source_url=URL,apply_url=URL,checked_at=p.snapshot.checked_at,seniority="internship",requirements=[
            Fact(name="skills",value=["Python","algorithms"],kind="requirement",status="known",
                 excerpt="Basic qualifications: Python and algorithms required.",source_url=URL,source_id="source-test")])
    run=ledger.enqueue(hunt["id"],TOKEN);ledger.claim(run["id"])
    ledger.finish(run["id"],EngineResult(listings=[listing],pages=[p]))
    return hunt,listing


def test_select_novel_listing_creates_source_backed_graph_preparation(api):
    client,graph,ledger,_=api;hunt,listing=seed(ledger)
    headers={"X-Scout-Client":TOKEN}
    response=client.post(f"/api/hunts/{hunt['id']}/select",headers=headers,json={"listing_ids":[listing.id]})
    assert response.status_code==200,response.text
    ids=response.json()["selected_ids"]
    context=graph.context(ids)
    assert any("Python" in task.title for task in context.tasks)
    assert any(e.excerpt and "Python" in e.excerpt for e in context.evidence)
    response_plan=client.post("/api/plan",json={"selected_ids":ids})
    assert response_plan.status_code==200,response_plan.text
    plan=response_plan.json()
    assert any("Python" in task["title"] for task in plan["tasks"])
    assert plan["targets"][0]["schedule_status"]=="cannot_certify"
    assert any("discovery" in op for op in response.json()["opportunities"])


def test_discovery_requirements_survive_selection_graph_plan_and_readback(api):
    client,graph,ledger,monkeypatch=api
    hunt=ledger.create_hunt(TOKEN,DiscoveryPreferences(roles=['software engineer']))
    p=WebPage(snapshot=SourceSnapshot(id='source-roadmap',url=URL,title='Software Engineer Intern',
        text='# Software Engineer Intern\nPython required.\nJavaScript preferred.\nSelection includes a coding challenge.\n'),requested_url=URL)
    facts=[Fact(name=name,value=value,kind=kind,status='known',excerpt=quote,source_url=URL,source_id=p.snapshot.id)
        for name,value,kind,quote in [('skills',['Python'],'requirement','Python required.'),
            ('preferred_skills',['JavaScript'],'preference','JavaScript preferred.'),
            ('application_process','Selection includes a coding challenge.','information','Selection includes a coding challenge.')]]
    listing=DiscoveryListing(id='listing-roadmap',title=p.snapshot.title,organization='Example',
        source_url=URL,apply_url=URL,checked_at=p.snapshot.checked_at,requirements=facts,enrichment_status='complete')
    run=ledger.enqueue(hunt['id'],TOKEN);ledger.claim(run['id'])
    ledger.finish(run['id'],EngineResult(listings=[listing],pages=[p]))
    import app.discovery.extract as extract
    monkeypatch.setattr(extract,'ListingExtractor',lambda *args:pytest.fail('Selection repeated discovery extraction'))
    headers={'X-Scout-Client':TOKEN}
    response=client.post(f"/api/hunts/{hunt['id']}/select",headers=headers,json={'listing_ids':[listing.id]})
    assert response.status_code==200,response.text
    ids=response.json()['selected_ids']
    context=graph.context(ids)
    observed={f.name:f for f in context.opportunities[0].facts}
    assert observed['skills'].value==['Python'] and observed['skills'].kind=='requirement'
    assert observed['preferred_skills'].kind=='preference'
    assert observed['application_process'].excerpt=='Selection includes a coding challenge.'
    response=client.post('/api/plan',headers=headers,json={'selected_ids':ids})
    assert response.status_code==200,response.text
    plan=response.json()
    assert any('Python' in task['title'] for task in plan['tasks'])
    assert any('Python required.' in e.excerpt for e in context.evidence)
    reloaded=client.get('/api/plan/latest',headers=headers).json()['plan']
    assert reloaded['id']==plan['id']


def test_browser_scoped_hunt_selection_and_listing_flags(api):
    client,_,ledger,_=api;hunt,listing=seed(ledger)
    path=f"/api/hunts/{hunt['id']}"
    assert client.get(path).status_code==400
    assert client.get(path,headers={"X-Scout-Client":"anotherbrowser12345678901234567890"}).status_code==404
    response=client.post(f"{path}/listings/{listing.id}/flags",headers={"X-Scout-Client":TOKEN},json={"saved":True,"hidden":True})
    assert response.status_code==200
    record=client.get(path,headers={"X-Scout-Client":TOKEN}).json()
    assert record["result"]["listings"][0]["saved"]
    assert record["result"]["listings"][0]["hidden"]


def test_scout_listing_summary_sources_routes_and_owner_boundary(api):
    client,_,ledger,_=api;hunt,listing=seed(ledger)
    headers={"X-Scout-Client":TOKEN}
    path=f"/api/hunts/{hunt['id']}"
    response=client.get(path+"/listings",headers=headers,params={"view":"new","q":"software"})
    assert response.status_code==200 and response.json()["listings"][0]["id"]==listing.id
    assert client.get(path+"/listings",headers=headers,params={"view":"wrong"}).status_code==400
    assert client.get(path+"/summary",headers=headers).json()["total"]==1
    assert client.get(path+"/sources",headers=headers).json()["sources"][0]["url"]==URL
    assert client.get(path+"/sources",headers={"X-Scout-Client":"anotherbrowser12345678901234567890"}).status_code==404


def test_multiple_feed_rows_bind_selected_target_to_its_own_evidence(api):
    client,graph,ledger,_=api
    hunt=ledger.create_hunt(TOKEN,DiscoveryPreferences(roles=["software engineer"]))
    url="https://api.lever.co/v0/postings/example?mode=json"
    listings=[];pages=[]
    for identifier,skill in [("one","Python"),("two","Java")]:
        title=f"Software Intern {identifier}"
        quote=f"{skill} programming required."
        snapshot=SourceSnapshot(id="feed-source",url=url,title=title,text=f"# {title}\nEvidence view: decoded public ATS feed row.\n{quote}")
        pages.append(WebPage(snapshot=snapshot,requested_url=url))
        listings.append(DiscoveryListing(id=identifier,title=title,organization="Example",source_url=url,
            apply_url=f"https://jobs.lever.co/example/{identifier}",checked_at=snapshot.checked_at,
            requirements=[Fact(name="skills",value=[skill],status="known",kind="requirement",excerpt=quote,source_url=url,source_id=snapshot.id)]))
    run=ledger.enqueue(hunt["id"],TOKEN);ledger.claim(run["id"])
    ledger.finish(run["id"],EngineResult(listings=listings,pages=pages))
    response=client.post(f"/api/hunts/{hunt['id']}/select",headers={"X-Scout-Client":TOKEN},json={"listing_ids":["one","two"]})
    assert response.status_code==200,response.text
    opportunities=response.json()["opportunities"]
    actual={o["program"]:next(f for f in o["facts"] if f["name"]=="skills") for o in opportunities}
    assert actual["Software Intern one"]["value"]==["Python"]
    assert actual["Software Intern two"]["value"]==["Java"]
    assert all(f["status"]=="known" for f in actual.values())


def test_selected_target_survives_ai_enrichment_failure_and_retains_listing(api):
    import app.discovery.extract as extract
    from app.discovery.contracts import ExtractionResult
    client,graph,ledger,monkeypatch=api;hunt,listing=seed(ledger)
    with ledger._db() as db:
        import json
        value=json.loads(db.execute("SELECT result FROM hunts WHERE id=?",(hunt['id'],)).fetchone()[0])
        value['listings'][0]['requirements']=[]
        db.execute("UPDATE hunts SET result=? WHERE id=?",(json.dumps(value),hunt['id']))
    class Extractor:
        def __init__(self,*args):pass
        def extract(self,*args,**kwargs):return ExtractionResult(warnings=["AI quota unavailable; requirements unknown."])
    monkeypatch.setattr(extract,'ListingExtractor',Extractor)
    response=client.post(f"/api/hunts/{hunt['id']}/select",headers={"X-Scout-Client":TOKEN},json={"listing_ids":[listing.id]})
    assert response.status_code==200,response.text
    assert response.json()['enrichment_warnings']
    ids=response.json()['selected_ids']
    assert graph.get_opportunity(ids[0])
    record=client.get(f"/api/hunts/{hunt['id']}",headers={"X-Scout-Client":TOKEN}).json()
    assert record['result']['listings'][0]['id']==listing.id
    plan=client.post('/api/plan',json={'selected_ids':ids}).json()
    assert plan['targets'][0]['schedule_status']=='cannot_certify'


def test_historical_listing_cannot_restore_known_facts_without_revalidation(api):
    import json
    import app.discovery.provider as provider
    client,graph,ledger,monkeypatch=api;hunt,listing=seed(ledger)
    with ledger._db() as db:
        result=json.loads(db.execute('SELECT result FROM hunts WHERE id=?',(hunt['id'],)).fetchone()[0])
        result['listings'][0]['verification']='uncertain'
        db.execute('UPDATE hunts SET result=? WHERE id=?',(json.dumps(result),hunt['id']))
    class Web:
        def __init__(self,*args):pass
        def fetch(self,urls,**kwargs):return [],{URL:'Source unavailable'}
    monkeypatch.setattr(provider,'DiscoveryWebClient',Web)
    response=client.post(f"/api/hunts/{hunt['id']}/select",headers={'X-Scout-Client':TOKEN},json={'listing_ids':[listing.id]})
    assert response.status_code==200,response.text
    assert all(f['status']=='unknown' for f in response.json()['opportunities'][0]['facts'])
    assert response.json()['enrichment_warnings']


def test_selected_cohort_is_preserved_if_enrichment_does_not_name_a_cohort(api):
    import json
    import app.discovery.extract as extract
    from app.discovery.contracts import ExtractionResult
    client,graph,ledger,monkeypatch=api;hunt,listing=seed(ledger)
    with ledger._db() as db:
        result=json.loads(db.execute('SELECT result FROM hunts WHERE id=?',(hunt['id'],)).fetchone()[0])
        result['listings'][0].update(requirements=[],cycle='Summer 2027')
        db.execute('UPDATE hunts SET result=? WHERE id=?',(json.dumps(result),hunt['id']))
    class Extractor:
        def __init__(self,*args):pass
        def extract(self,*args,**kwargs):return ExtractionResult(page_type='posting',listings=[listing.model_copy(update={'cycle':'unknown'})])
    monkeypatch.setattr(extract,'ListingExtractor',Extractor)
    response=client.post(f"/api/hunts/{hunt['id']}/select",headers={'X-Scout-Client':TOKEN},json={'listing_ids':[listing.id]})
    assert response.status_code==200,response.text
    assert response.json()['opportunities'][0]['cycle']=='Summer 2027'


def test_requested_run_is_queued_without_inlining_network(api):
    client,_,ledger,monkeypatch=api
    class Worker:
        def __init__(self):self.calls=[]
        def submit(self,*args):self.calls.append(args)
    worker=Worker();monkeypatch.setattr(main,"discovery_workers",worker)
    response=client.post("/api/hunts",headers={"X-Scout-Client":TOKEN},json={"preferences":{"roles":["robotics intern"]}})
    assert response.status_code==200,response.text
    assert response.json()["run"]["status"]=="queued"
    assert len(worker.calls)<=1  # The persistent drainer owns scheduling, not this request.
    assert not ledger.hunt(response.json()["hunt"]["id"],TOKEN)["result"]


def test_generic_refresh_preserves_target_identity_and_noop_plan(api):
    from app.discovery.contracts import ExtractionResult
    import app.discovery.provider as provider
    import app.discovery.extract as extract
    client,graph,ledger,monkeypatch=api;hunt,listing=seed(ledger)
    response=client.post(f"/api/hunts/{hunt['id']}/select",headers={"X-Scout-Client":TOKEN},json={"listing_ids":[listing.id]})
    assert response.status_code==200,response.text
    ids=response.json()["selected_ids"]
    plan=client.post("/api/plan",json={"selected_ids":ids}).json()
    p=WebPage.model_validate(ledger.hunt(hunt["id"],TOKEN)["result"]["pages"][0])
    class Web:
        def __init__(self,*args):pass
        def fetch(self,urls):return [p],{}
    class Extractor:
        def __init__(self,*args):pass
        def extract(self,*args):return ExtractionResult(page_type="posting",listings=[listing])
    monkeypatch.setattr(provider,"DiscoveryWebClient",Web)
    monkeypatch.setattr(extract,"ListingExtractor",Extractor)
    refreshed=client.post("/api/refresh",json={"url":URL})
    assert refreshed.status_code==200,refreshed.text
    assert refreshed.json()["opportunities"][0]["id"]==ids[0]
    assert graph.latest_plan(plan["profile"]["id"]).status=="proposed"
    assert not any(i["semantic_change"] for i in refreshed.json()["impacts"])


def test_worker_executes_queued_run_and_records_terminal_result(api):
    client,_,ledger,monkeypatch=api
    hunt=ledger.create_hunt(TOKEN,DiscoveryPreferences(roles=["software engineer"]))
    run=ledger.enqueue(hunt["id"],TOKEN)
    class Engine:
        def __init__(self,*args):pass
        def run(self,preferences,*,previous,previous_pages,on_event):
            assert preferences.roles==["software engineer"] and previous==[] and previous_pages==[]
            on_event(RunEvent(stage="search",message="Mocked worker integration stage"))
            return EngineResult()
    monkeypatch.setattr(main,"DiscoveryEngine",Engine)
    main.execute_discovery(run["id"])
    response=client.get(f"/api/discovery-runs/{run['id']}",headers={"X-Scout-Client":TOKEN})
    assert response.status_code==200
    assert response.json()["status"]=="completed"
    assert response.json()["events"][0]["stage"]=="search"


def test_normal_plans_are_scoped_to_browser_and_do_not_restore_demo_progress(api):
    client,graph,ledger,monkeypatch=api
    monkeypatch.setattr(main,"settings",replace(settings,demo_tools_enabled=False))
    hunt,listing=seed(ledger)
    owner={"X-Scout-Client":TOKEN}
    other={"X-Scout-Client":"otherbrowser12345678901234567890"}
    selected=client.post(f"/api/hunts/{hunt['id']}/select",headers=owner,json={"listing_ids":[listing.id]})
    assert selected.status_code==200,selected.text
    ids=selected.json()["selected_ids"]
    forged={"selected_ids":ids,"profile":{"id":"demo-student","synthetic":False,"degree":"BTech",
        "year":2,"total_years":4,"weekly_hours":4,"start_date":"2026-10-19","exam_weeks":[]}}
    proposal=client.post("/api/plan",headers=owner,json=forged)
    assert proposal.status_code==200,proposal.text
    value=proposal.json()
    assert value["profile"]["id"]==main.preparation_profile_id(TOKEN)
    assert value["profile"]["year"]==2 and value["profile"]["degree"]=="BTech"
    assert not value["profile"]["synthetic"] and not value["profile"]["completed_task_ids"]
    assert TOKEN not in str(value)
    assert client.get("/api/plan/latest",headers=other).json()=={"plan":None}
    assert client.get("/api/plan/latest",headers=other,params={"profile_id":value["profile"]["id"]}).status_code==404
    assert client.post(f"/api/plan/{value['id']}/accept",headers=other).status_code==404
    assert client.post(f"/api/plan/{value['id']}/accept",headers=owner).status_code==200
    assert client.get("/api/plan/latest",headers=owner).json()["plan"]["status"]=="accepted"
    assert client.post("/api/plan",json=forged).status_code==400
    assert client.post("/api/plan",headers=owner,json={**forged,"profile":{"synthetic":True}}).status_code==400
    assert client.post("/api/examples").status_code==404
    assert client.post("/api/simulate",json={**forged,"opportunity_id":ids[0]}).status_code==404


def test_new_user_profile_does_not_guess_degree_or_exam_week(api):
    client,graph,ledger,monkeypatch=api
    monkeypatch.setattr(main,"settings",replace(settings,demo_tools_enabled=False))
    hunt,listing=seed(ledger)
    headers={"X-Scout-Client":TOKEN}
    ids=client.post(f"/api/hunts/{hunt['id']}/select",headers=headers,json={"listing_ids":[listing.id]}).json()["selected_ids"]
    value=client.post("/api/plan",headers=headers,json={"selected_ids":ids}).json()
    assert value["profile"]["degree"] is None and value["profile"]["year"] is None
    assert value["profile"]["exam_weeks"]==[]


def test_strict_hunt_views_use_source_evidence_and_preserve_review_candidates(api):
    client,graph,ledger,_=api
    hunt=ledger.create_hunt(TOKEN,DiscoveryPreferences(roles=['software intern'],locations=['Japan'],funding='fully_funded'))
    from app.discovery.basic import source_listing
    from app.discovery.contracts import SourceLead
    values=[]; pages=[]
    for identifier,place,benefits in [
        ('match','Tokyo, Japan','Stipend is provided. Accommodation is provided. Round-trip flights are reimbursed.'),
        ('foreign','Berlin, Germany','Stipend is provided. Accommodation is provided. Round-trip flights are reimbursed.'),
        ('partial','Tokyo, Japan','Stipend is provided. Round-trip flights are reimbursed.')]:
        url=f'https://employer.example/jobs/{identifier}/software-intern'
        text=f'# Software Intern\nLocation: {place}\n{benefits}\nApplication fee: 25 USD.'
        p=WebPage(snapshot=SourceSnapshot(id=identifier,url=url,title='Software Intern',text=text),requested_url=url)
        pages.append(p)
        value=source_listing(SourceLead(url=url,title='Software Intern',kind='posting'),p)
        value.id=identifier
        values.append(value)
    run=ledger.enqueue(hunt['id'],TOKEN); assert ledger.claim(run['id'])
    ledger.finish(run['id'],EngineResult(listings=values,pages=pages))
    path=f"/api/hunts/{hunt['id']}"; headers={'X-Scout-Client':TOKEN}
    matches=client.get(path+'/listings',headers=headers).json()['listings']
    assert [v['id'] for v in matches]==['match']
    assert matches[0]['constraint_status']=='match' and matches[0]['filter_evidence']['round_trip_travel']
    review=client.get(path+'/listings',headers=headers,params={'view':'review'}).json()['listings']
    assert [v['id'] for v in review]==['partial']
    assert any('Accommodation' in reason for reason in review[0]['constraint_reasons'])
    summary=client.get(path+'/summary',headers=headers).json()
    assert summary['total']==1 and summary['needs_review']==1
    assert client.get(path+'/listings',headers=headers,params={'funding':'paid'}).json()['listings']==matches
    assert client.get(path+'/listings',headers={'X-Scout-Client':'otherbrowser12345678901234567890'}).status_code==404


def test_interest_scenarios_endpoint_is_authored_and_does_not_start_discovery(api):
    client,_,ledger,_=api
    value=client.get('/api/interest-scenarios').json()
    assert len(value['scenarios'])==12 and len(value['directions'])==6
    assert not ledger.queued()
