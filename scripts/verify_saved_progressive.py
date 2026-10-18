"""Revalidate the saved real source result and graph connection without network AI."""
import json
from pathlib import Path
from dataclasses import replace
from uuid import uuid4
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.config import settings
from app.discovery.contracts import EngineResult
from app.discovery.bridge import _scope,review_listing_requirements,listing_to_opportunities
from app.discovery.extract import source_conditions
from app.graph import GraphStore
from app.models import ProfileState
from app.planner import build_plan

r=EngineResult.model_validate(json.loads((ROOT/'reports/local/progressive-live-proof.json').read_text())['result'])
v=r.listings[0];p=r.pages[0]
facts=source_conditions(_scope(v,p),p)
v.requirements=[f for f in v.requirements if f.name not in {x.name for x in facts}]+facts
v.enrichment_status='partial'
v=review_listing_requirements(v,p)
target,=listing_to_opportunities(v,p)
name='just_chill_saved_progressive_test_'+uuid4().hex
graph=GraphStore(replace(settings,db_graph=name))
try:
    graph.upsert_opportunity(target,p.snapshot)
    context=graph.context([target.id])
    plan=build_plan(context,ProfileState(id='synthetic-saved-source-proof',start_date='2026-10-19'))
    graph.save_plan(plan)
    assert graph.get_plan(plan.id).id==plan.id
    assert context.evidence and any('proficiency' in e.excerpt for e in context.evidence)
    report={'mode':'saved real TinyFish page and real Groq observations revalidated locally; no new provider calls',
        'known_facts':sum(f.status=='known' for f in target.facts),'tasks':len(context.tasks),
        'evidence_paths':len(context.evidence),'schedule_status':plan.targets[0].schedule_status,
        'listing':v.model_dump(mode='json'),'plan':plan.model_dump(mode='json'),'result':'passed'}
    (ROOT/'reports/local/saved-progressive-graph-proof.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:report[k] for k in ('result','known_facts','tasks','evidence_paths','schedule_status')},indent=2))
finally:
    assert name.startswith('just_chill_saved_progressive_test_') and name!=settings.db_graph
    db=graph._db()
    if name in db.list_graphs():db.select_graph(name).delete()
    db.close()
