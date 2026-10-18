"""Bounded real discovery→requirements→FalkorDB→preparation proof.

Uses real TinyFish Search/Fetch and Groq. No Agent spend and no main graph writes.
Only the explicitly created disposable graph is deleted after proof. The fetched
source/result report is stored under ignored reports/local, not a public artifact.
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from app.config import settings
from app.discovery.bridge import listing_to_opportunities
from app.discovery.contracts import DiscoveryPreferences, RunBudget
from app.discovery.engine import DiscoveryEngine
from app.discovery.state import DiscoveryState
from app.graph import GraphStore
from app.models import ProfileState
from app.planner import build_plan


def main():
    name="just_chill_scout_live_test_"+uuid4().hex
    config=replace(settings,db_graph=name,tinyfish_agent_enabled=False)
    output=ROOT/"reports/local"
    output.mkdir(parents=True,exist_ok=True)
    ledger=DiscoveryState(str(output/"scout-proof.sqlite"))
    graph=GraphStore(config)
    assert graph.health()["status"]=="ok"
    try:
        start=time.monotonic()
        result=DiscoveryEngine(config,ledger).run(
            DiscoveryPreferences(roles=["software engineering intern"],locations=["Germany"],companies=["Amazon"],opportunity_types=["company_roles"]),
            budget=RunBudget(max_searches=3,max_fetch_urls=8,max_extractions=3,soft_deadline_ms=90000,hard_deadline_ms=120000),
            on_event=lambda event: print(f"{event.stage}: {event.message}",flush=True),
        )
        # Preserve failures for diagnosis without repeating live provider work.
        (output/"scout-live-engine-result.json").write_text(result.model_dump_json(indent=2))
        pages={page.snapshot.url:page for page in result.pages}
        choices=[listing for listing in result.listings if listing.requirements and listing.call_status!="closed"]
        assert choices,"No live source-backed candidate; inspect the explicit source/provider gaps."
        listing=next((l for l in choices if "amazon" in l.source_url.lower()),choices[0])
        page=pages.get(listing.source_url)
        targets=listing_to_opportunities(listing,page)
        assert len(targets)==1,"The bounded proof requires one explicit target/cohort."
        target=targets[0]
        graph.upsert_opportunity(target,page.snapshot if page else None)
        context=graph.context([target.id])
        plan=build_plan(context,ProfileState(id="synthetic-live-proof"))
        assert any(t.artifact_type in {"skill_practice","skill_evidence_review","experience_evidence_review"} for t in context.tasks),"Generic preparation is still verify-only."
        assert any(e.excerpt for e in context.evidence),"Graph returned no source-backed evidence."
        report={"mode":"real Search/Fetch/Groq; no Agent; disposable graph", "seconds":round(time.monotonic()-start,2),
                "result":result.model_dump(mode="json"),"target":target.model_dump(mode="json"),
                "plan":plan.model_dump(mode="json"),"graph_tasks":len(context.tasks),"graph_evidence":len(context.evidence)}
        (output/"scout-live-proof.json").write_text(json.dumps(report,indent=2))
        print(json.dumps({"result":"passed","seconds":report["seconds"],"listing":listing.title,"listing_count":len(result.listings),
            "typed_known_facts":sum(f.status=="known" for f in target.facts),"graph_tasks":len(context.tasks),"graph_evidence":len(context.evidence),
            "schedule_status":plan.targets[0].schedule_status,"usage":result.usage,"partial":result.partial,
            "errors":result.errors,"main_graph_unchanged":True,"agent_runs":0},indent=2))
    finally:
        assert name.startswith("just_chill_scout_live_test_") and name!=settings.db_graph
        db=graph._db()
        if name in db.list_graphs():db.select_graph(name).delete()
        db.close()


if __name__=="__main__":main()
