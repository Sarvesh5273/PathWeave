"""One fresh Search plus cached Agent link -> fresh Fetch/Groq -> disposable graph.

Never starts a paid Agent. Saves the actual outcome before assertions for diagnosis.
Does not change the main hunt state or graph.
"""
from dataclasses import replace
import json
from pathlib import Path
import sys
import time
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.config import settings
from app.discovery.browser import BrowserFallback
from app.discovery.bridge import listing_to_opportunities
from app.discovery.contracts import DiscoveryPreferences, SourceLead
from app.discovery.contracts import EngineResult
from app.discovery.progressive import DiscoveryEngine
from app.discovery.provider import DiscoveryWebClient
from app.discovery.state import DiscoveryState
from app.graph import GraphStore
from app.models import ProfileState
from app.planner import build_plan


def main():
    output=ROOT/'reports/local'
    old=json.loads((output/'tinyfish-browser-proof.json').read_text())
    assert old['status']=='COMPLETED'
    opening=SourceLead.model_validate(old['openings'][0])
    portal=SourceLead(url=old['portal'],title='Notion Careers',organization='Notion',kind='board')
    prefs=DiscoveryPreferences.model_validate(old['preferences'])
    name='just_chill_progressive_live_test_'+uuid4().hex
    config=replace(settings,tinyfish_agent_enabled=False,db_graph=name,
        discovery_enrichment_pages=1,discovery_enrichment_seconds=150)
    ledger=DiscoveryState(str(output/('progressive-proof-'+uuid4().hex+'.sqlite')))
    browser=BrowserFallback(config)
    ledger.cache('agent:'+browser.cache_key(portal,prefs),[opening.model_dump()],86400)
    class Web:
        def __init__(self): self.client=DiscoveryWebClient(config);self.searches=0
        def search(self,task):
            if self.searches:return []
            self.searches+=1
            observed=self.client.search(task)
            (output/'progressive-proof-search.json').write_text(json.dumps([v.model_dump() for v in observed],indent=2))
            # Only the already observed named portal is allowed in this bounded proof.
            return [portal]
        def fetch(self,urls,**kwargs):
            actual=[url for url in urls if url.split('?')[0]==opening.url.split('?')[0]]
            return self.client.fetch(actual,ttl=0) if actual else ([],{})
    web=Web();progress=[]
    start=time.monotonic()
    engine=DiscoveryEngine(config,ledger,web=web,browser=browser)
    resume='--reuse-source' in sys.argv
    if resume:
        prior=EngineResult.model_validate(json.loads((output/'progressive-live-proof.json').read_text())['result'])
        for v in prior.listings:v.requirements=[];v.enrichment_status='pending'
        class Finder:
            def run(self, preferences, on_progress, **kwargs):
                on_progress(prior.model_copy(deep=True))
                return prior.model_copy(deep=True)
        engine.finder=Finder()
        def reuse_fit(batch,*args,**kwargs):
            return [v.model_copy(update={'score_mode':'cached'}) for v in batch],[]
        engine.scorer=reuse_fit
    result=engine.run(prefs,
        on_progress=lambda r:progress.append({'count':len(r.listings),'known':sum(f.status=='known' for v in r.listings for f in v.requirements)}),
        on_event=lambda e:print(e.stage+': '+e.message,flush=True))
    report={'mode':'saved public page and prior real Groq score; one targeted Groq extraction; isolated graph' if resume else 'one fresh Search; reused completed Agent links; fresh Fetch/Groq; isolated graph',
        'seconds':round(time.monotonic()-start,2),'progress':progress,'result':result.model_dump(mode='json'),
        'actual_searches':web.searches,'new_agent_runs':result.usage.get('agent_runs',0)}
    path=output/('progressive-source-recheck.json' if resume else 'progressive-live-proof.json')
    path.write_text(json.dumps(report,indent=2))
    assert result.listings and result.usage['agent_runs']==0
    chosen=next((v for v in result.listings if any(f.status=='known' and f.kind=='requirement' for f in v.requirements)),None)
    assert chosen,'No supported requirement; inspect saved result instead of repeating the run.'
    assert chosen.score_mode in {'groq','cached'},'No actual preference verdict; inspect saved quota outcome.'
    p=next(p for p in result.pages if p.snapshot.url==chosen.source_url)
    targets=listing_to_opportunities(chosen,p)
    graph=GraphStore(config)
    try:
        assert graph.health()['status']=='ok'
        for target in targets:graph.upsert_opportunity(target,p.snapshot)
        context=graph.context([v.id for v in targets])
        plan=build_plan(context,ProfileState(id='synthetic-progressive-proof',start_date='2026-10-19'))
        graph.save_plan(plan)
        stored=graph.get_plan(plan.id)
        assert stored.id==plan.id
        assert any(e.excerpt for e in context.evidence)
        report.update(plan=plan.model_dump(mode='json'),graph_known_facts=sum(f.status=='known' for v in context.opportunities for f in v.facts),
            graph_tasks=len(context.tasks),graph_evidence=len(context.evidence),result_status='passed')
        path.write_text(json.dumps(report,indent=2))
        print(json.dumps({'result':'passed','seconds':report['seconds'],'requirements':len(chosen.requirements),
            'score_mode':chosen.score_mode,'enrichment':chosen.enrichment_status,'graph_tasks':len(context.tasks),
            'main_state_unchanged':True,'new_agent_runs':0,'usage':result.usage},indent=2))
    finally:
        assert name.startswith('just_chill_progressive_live_test_') and name!=settings.db_graph
        db=graph._db()
        if name in db.list_graphs():db.select_graph(name).delete()
        db.close()


if __name__=='__main__':main()
