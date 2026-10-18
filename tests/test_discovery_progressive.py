from dataclasses import replace
import hashlib

import httpx
import pytest

from app.config import settings
from app.discovery.basic import source_listing
from app.discovery.bridge import listing_to_opportunities
from app.discovery.contracts import DiscoveryPreferences, EngineResult, ExtractionResult, SourceLead, WebPage
from app.discovery.extract import ListingExtractor
from app.discovery.preferences import evidence_status, score_preferences
from app.discovery.progressive import DiscoveryEngine, fit_rows
from app.discovery.state import DiscoveryState
from app.models import Fact, SourceSnapshot

URL = 'https://company.example/jobs/1001/software-engineer-intern'
TEXT = ('# Software Engineer Intern\nLocation: Tokyo, Japan\n# Basic qualifications\n'
        'Python required.\n# Preferred qualifications\nJavaScript preferred.\n'
        '# How to Apply\nSubmit a CV. Selection includes a coding challenge.\n')


def page(text=TEXT, url=URL):
    return WebPage(snapshot=SourceSnapshot(id='source-test', url=url, title='Software Engineer Intern',
        text=text, content_hash=hashlib.sha256(text.encode()).hexdigest()), requested_url=url)


def listing(p):
    return source_listing(SourceLead(url=p.snapshot.url, title=p.snapshot.title, kind='posting'), p)


class Finder:
    def __init__(self, result): self.result = result
    def run(self, preferences, on_progress, **kwargs):
        on_progress(self.result.model_copy(deep=True))
        return self.result.model_copy(deep=True)


class Extractor:
    def __init__(self, progress, partial=False, fail=False):
        self.calls = 0; self.progress = progress; self.partial = partial; self.fail = fail
    def extract_selected(self, p, v, preferences, on_call, **kwargs):
        early=next((r for r in self.progress if r.listings),None)
        assert early and early.listings[0].requirements == []
        self.calls += 1; on_call()
        if self.fail and self.calls == 1:
            return ExtractionResult(warnings=['Groq output truncated; requirements unknown.'])
        facts = [Fact(name=name, value=value, kind=kind, status='known', excerpt=excerpt,
                      source_url=p.snapshot.url, source_id=p.snapshot.id)
                 for name,value,kind,excerpt in [
                     ('skills',['Python'],'requirement','Python required.'),
                     ('skills',['JavaScript'],'preference','JavaScript preferred.'),
                     ('application_process','Selection includes a coding challenge.','information','Selection includes a coding challenge.')]]
        if self.partial:
            facts.append(Fact(name='requirements_review', status='unknown', kind='requirement'))
        return ExtractionResult(listings=[v.model_copy(update={'requirements':facts,
            'enrichment_status':'partial' if self.partial else 'complete'})])


def setup(tmp_path, *, text=TEXT, count=1, partial=False, fail=False, key='offline'):
    progress=[]
    extractor=Extractor(progress, partial, fail)
    config=replace(settings, groq_key=key, tinyfish_agent_enabled=False,
                   discovery_enrichment_seconds=150, discovery_enrichment_pages=6)
    ledger=DiscoveryState(str(tmp_path/'test.sqlite'))
    engine=DiscoveryEngine(config, ledger, extractor=extractor,
        scorer=lambda batch,prefs,*args,**kwargs:score_preferences(batch,prefs))
    pages=[page(text, URL+str(i)) for i in range(count)]
    engine.finder=Finder(EngineResult(listings=[listing(p) for p in pages], pages=pages))
    return engine, ledger, extractor, progress


def test_early_results_then_required_preferred_and_selection_steps_before_selection(tmp_path):
    engine,_,extractor,progress=setup(tmp_path)
    result=engine.run(DiscoveryPreferences(roles=['software engineer']),on_progress=progress.append)
    v=result.listings[0]
    assert extractor.calls == 1 and result.usage['extractions'] == 1
    assert v.enrichment_status == 'complete'
    assert {f.name:f.kind for f in v.requirements}['preferred_skills'] == 'preference'
    assert any(f.name=='application_process' and 'coding challenge' in f.value for f in v.requirements)
    target,=listing_to_opportunities(v,result.pages[0])
    assert {f.name:f.value for f in target.facts}['skills'] == ['Python']
    assert {f.name:f.value for f in target.facts}['preferred_skills'] == ['JavaScript']


def test_complete_content_cache_avoids_model_but_partial_cache_does_not(tmp_path):
    engine,ledger,extractor,progress=setup(tmp_path)
    prefs=DiscoveryPreferences(roles=['software engineer'])
    engine.run(prefs,on_progress=progress.append)
    second=engine.run(prefs,on_progress=progress.append)
    assert extractor.calls == 1 and second.usage['extraction_cached'] == 1
    with ledger._db() as db:
        rows=db.execute("SELECT key FROM cache WHERE key LIKE 'progressive-extract-%'").fetchall()
    for row in rows: ledger.delete_cache(row[0])
    extractor.partial=True
    engine.run(prefs,on_progress=progress.append)
    fourth=engine.run(prefs,on_progress=progress.append)
    assert extractor.calls == 3 and fourth.listings[0].enrichment_status=='partial'
    assert fourth.listings[0].evidence_completeness['requirements']=='partial'


def test_one_failed_extraction_preserves_all_and_other_source_enrichment(tmp_path):
    engine,_,_,progress=setup(tmp_path,count=2,fail=True)
    result=engine.run(DiscoveryPreferences(roles=['software engineer']),on_progress=progress.append)
    assert len(result.listings)==2
    assert {v.enrichment_status for v in result.listings}=={'failed','complete'}
    assert result.partial


def test_no_ai_key_makes_zero_calls_and_preserves_unknowns(tmp_path):
    engine,_,extractor,progress=setup(tmp_path,key='')
    result=engine.run(DiscoveryPreferences(roles=['software engineer']),on_progress=progress.append)
    assert extractor.calls==0 and result.usage['ai_attempts']==0
    assert result.listings[0].score_mode=='rules'
    assert result.listings[0].evidence_completeness['requirements']=='unconfirmed'


def test_invalid_score_ids_or_injected_metadata_cannot_remove_or_rewrite_candidates(tmp_path):
    engine,_,_,progress=setup(tmp_path)
    def scorer(batch,prefs,*args,**kwargs):
        return [batch[0].model_copy(update={'id':'phantom','locations':['United States']})],[]
    engine.scorer=scorer
    result=engine.run(DiscoveryPreferences(roles=['software engineer'],locations=['Japan']),on_progress=progress.append)
    assert len(result.listings)==1 and result.listings[0].locations==['Tokyo, Japan']
    assert result.listings[0].score_mode=='rules' and result.partial


def test_cache_score_duplicate_ids_and_bad_values_are_rejected():
    p=page(); batch=[listing(p),listing(page(url=URL+'2'))]
    row={'id':batch[0].id,'score':100,'score_breakdown':{'role':70},'reasons':[]}
    assert fit_rows([row,row],batch) is None
    assert fit_rows([{**row,'score':True}],batch[:1]) is None


def test_high_preference_fit_does_not_override_location_or_funding(tmp_path):
    engine,_,_,progress=setup(tmp_path,text=TEXT.replace('Tokyo, Japan','Toronto, Canada')+'Housing is not covered.\n')
    result=engine.run(DiscoveryPreferences(roles=['software engineer'],locations=['Japan'],funding='fully_funded'),on_progress=progress.append)
    v=result.listings[0]
    assert v.score>=60 and v.constraint_status=='excluded'
    assert v.evidence_completeness['housing']=='not_covered'
    assert v.evidence_completeness['requirements']=='reviewed'


def test_revalidated_requirement_invalid_value_cannot_become_complete(tmp_path):
    engine,_,_,progress=setup(tmp_path)
    v=engine.finder.result.listings[0]
    v.requirements=[Fact(name='skills',value=['Rust'],kind='requirement',status='known',
        excerpt='Python required.',source_url=v.source_url,source_id='source-test')]
    v.enrichment_status='complete'
    result=engine.run(DiscoveryPreferences(roles=['software engineer']),on_progress=progress.append)
    assert result.listings[0].enrichment_status=='partial'
    assert all(f.status=='unknown' for f in result.listings[0].requirements)
    assert result.listings[0].evidence_completeness['requirements']=='unconfirmed'


def test_evidence_completeness_requires_actual_facts():
    assert evidence_status(listing(page()).model_copy(update={'enrichment_status':'complete'})).evidence_completeness['requirements']=='unconfirmed'


def test_compact_groq_scoring_rejects_missing_and_duplicate_ids():
    import json
    batch=[listing(page()),listing(page(url=URL+'2'))]
    config=replace(settings,groq_key='offline-preference',groq_model='test-fit',
        discovery_ai_tpm=1_000_000,discovery_ai_output_tpm=1_000_000)
    def transport(rows):
        return httpx.MockTransport(lambda req:httpx.Response(200,json={'choices':[{'finish_reason':'stop',
            'message':{'content':json.dumps({'fits':rows})}}]}))
    prefs=DiscoveryPreferences(roles=['software engineer'])
    fitted,warnings=score_preferences(batch,prefs,config,transport=transport([[0,'strong','Matches role'],[1,'partial','Related work']]))
    assert all(v.score_mode=='groq' for v in fitted) and not warnings
    fitted,warnings=score_preferences(batch,prefs,config,transport=transport([[0,'strong','Matches role'],[0,'strong','Duplicate']]))
    assert len(fitted)==2 and all(v.score_mode=='rules' for v in fitted) and warnings


def test_cached_agent_links_are_fetched_and_enriched_without_new_browser_run(tmp_path):
    portal='https://jobs.ashbyhq.com/notion'
    url=portal+'/test-opening'
    p=page(url=url)
    class Web:
        def __init__(self): self.fetches=[]
        def search(self, task): return [SourceLead(url=portal,title='Notion Careers')]
        def fetch(self, urls, **kwargs):
            self.fetches.extend(urls)
            return [p for u in urls if u==url],{}
    class Browser:
        def cache_key(self,*args): return 'cached-notion'
        def find(self,*args,**kwargs): pytest.fail('Unexpected paid Agent run')
    web=Web()
    progress=[]; extractor=Extractor(progress)
    ledger=DiscoveryState(str(tmp_path/'agent.sqlite'))
    ledger.cache('agent:cached-notion',[SourceLead(url=url,title=p.snapshot.title,
        organization='Notion',kind='posting',via='agent').model_dump()],86400)
    config=replace(settings,groq_key='offline',tinyfish_agent_enabled=False)
    engine=DiscoveryEngine(config,ledger,web=web,browser=Browser(),extractor=extractor,
        scorer=lambda batch,prefs,*args,**kwargs:score_preferences(batch,prefs))
    result=engine.run(DiscoveryPreferences(roles=['software engineer'],companies=['Notion'],
        opportunity_types=['company_roles']),on_progress=progress.append)
    assert url in web.fetches and result.usage['agent_runs']==0
    assert result.listings[0].found_via=='agent' and result.listings[0].requirements


def test_source_metadata_and_pathway_qualifiers_are_kept_as_sourced_observations():
    import json
    text=('# Software Engineer Intern\nLocation: Tokyo, Japan\nRemote work available.\n'
          'Visa sponsorship is provided.\nApplication deadline: 2027-01-31.\n'
          '# Requirements\nFor Backend, Python is required; for Frontend, JavaScript is required.\n')
    p=page(text)
    rows=[['locations',['Tokyo','Japan'],'information',[1]],['work_mode','remote','information',[2]],
          ['visa_policy','Visa sponsorship is provided.','information',[3]],
          ['application_deadline_text','2027-01-31','information',[4]],
          ['pathway_requirements','For Backend, Python is required; for Frontend, JavaScript is required.','requirement',[6]]]
    config=replace(settings,groq_key='offline-metadata',groq_model='test-metadata',
        discovery_ai_tpm=1_000_000,discovery_ai_output_tpm=1_000_000)
    transport=httpx.MockTransport(lambda req:httpx.Response(200,json={'choices':[{'finish_reason':'stop',
        'message':{'content':json.dumps({'complete':True,'facts':rows})}}]}))
    out=ListingExtractor(config,transport).extract_selected(p,listing(p),DiscoveryPreferences(roles=['software engineer']))
    v=out.listings[0]
    assert v.locations==['Tokyo','Japan'] and v.work_mode=='remote' and v.visa_status=='sponsors'
    assert v.deadline_precision=='date' and '2027-01-31' in v.deadline_text
    target,=listing_to_opportunities(v,p)
    pathway=next(f for f in target.facts if f.name=='pathway_requirements')
    assert pathway.status=='known' and pathway.value==rows[-1][1]
    assert not any(f.status=='known' and f.name=='skills' for f in target.facts)


def test_sibling_posting_benefits_do_not_satisfy_strict_funding():
    from app.discovery.filters import source_filter_evidence
    p=page(TEXT+'# Robotics Internship\nStipend and housing are provided. Return airfare covered.\n')
    v=source_filter_evidence(listing(p),p)
    assert v.stipend is None and v.housing is None and v.round_trip_travel is None


def test_failed_groq_json_preserves_sourced_qualifications_and_safe_failure_reason():
    config=replace(settings,groq_key='offline-json-failure',groq_model='test-json-failure')
    transport=httpx.MockTransport(lambda req:httpx.Response(400,json={'error':{
        'code':'json_validate_failed','message':'secret provider details must not escape','failed_generation':'private'}}))
    out=ListingExtractor(config,transport).extract_selected(page(),listing(page()),DiscoveryPreferences(roles=['software engineer']))
    assert out.listings[0].enrichment_status=='partial'
    assert any(f.status=='known' and f.value=='Python required.' for f in out.listings[0].requirements)
    assert any('valid JSON' in w for w in out.warnings)
    assert not any('secret' in w or 'private' in w for w in out.warnings)
