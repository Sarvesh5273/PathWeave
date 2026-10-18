"""One actual application-key Agent fallback proof within the authorized $3 total.

Reads wallet before any metered request, verifies the exact account rate, and
reserves the documented 150-step default maximum ($2.40 at $0.016). Never retries
or adds funds. Pending run ID persists immediately so a broken SSE stream cannot
cause another paid start. Uses only a public careers portal, no profiles/logins.
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import httpx

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from app.config import settings
from app.discovery.browser import BrowserFallback
from app.discovery.contracts import DiscoveryPreferences, SourceLead
from app.discovery.provider import DiscoveryWebClient, ProviderError
from app.discovery.state import DiscoveryState


def main():
    # The shared app ledger keeps this proof and later fallback reservations together.
    ledger=DiscoveryState(settings.discovery_state_path)
    output=ROOT/"reports/local"
    output.mkdir(parents=True,exist_ok=True)
    prefs=DiscoveryPreferences(roles=["software engineering intern"],companies=["Notion"],remote_ok=True,opportunity_types=["company_roles"])
    lead=SourceLead(url="https://jobs.ashbyhq.com/notion",organization="Notion",kind="board")
    with httpx.Client(timeout=10,follow_redirects=False) as client:
        response=client.get("https://agent.tinyfish.ai/v1/wallet",headers={"X-API-Key":settings.tinyfish_key})
    if response.status_code!=200:
        raise SystemExit("Application account rate could not be verified; no Agent call made.")
    wallet=response.json()
    meter=next((r for r in wallet.get("rates",{}).get("meters",[]) if r.get("label")=="TinyFish Agent"),{})
    if meter.get("currency")!="USD" or meter.get("per")!="step":
        raise SystemExit("Unrecognized billing unit; no Agent call made.")
    price=Decimal(meter["unit_amount"])
    ceiling=price*150
    if not 0<ceiling<=Decimal("3") or Decimal(wallet["available_balance"])<ceiling:
        raise SystemExit("Verified maximum does not fit authorized/available funds; no Agent call made.")
    config=replace(settings,tinyfish_agent_enabled=True,tinyfish_agent_default_cap_verified=True,
                   tinyfish_agent_step_cap_verified=False,tinyfish_agent_max_steps=150,
                   tinyfish_agent_step_cost_usd=float(price),discovery_agent_budget_usd=3)
    browser=BrowserFallback(config)
    key="agent:"+browser.cache_key(lead,prefs)
    pending_key="pending:"+key
    if ledger.cached(key) is not None or ledger.cached(pending_key) is not None:
        raise SystemExit("Existing result/pending run found; no new paid start. Inspect/recover that run instead.")
    pages,failures=DiscoveryWebClient(settings).fetch([lead.url])
    # Scout deliberately routes this known unreadable ATS through the Agent path.
    if pages and any(p.snapshot.text.strip() for p in pages):
        print("Portal Fetch returned content; checking Agent parity explicitly rather than claiming Fetch failed.")
    if not ledger.acquire(pending_key,{"run_id":None,"lead":lead.model_dump(),"status":"reserved"},10**9):
        raise SystemExit("Another worker owns this goal; no paid start.")
    if not ledger.reserve("agent_session_usd",float(ceiling),3,window=10**15):
        ledger.delete_cache(pending_key)
        raise SystemExit("Authorized total Agent reservation exhausted; no paid start.")
    proof={"account_rate_usd_per_step":str(price),"documented_default_max_steps":150,
           "maximum_reserved_usd":str(ceiling),"total_authorized_usd":"3","fetch_errors":failures,
           "preferences":prefs.model_dump(),"portal":lead.url,"new_top_up":False}
    def started(run_id):
        proof["run_id"]=run_id
        ledger.cache(pending_key,{"run_id":run_id,"lead":lead.model_dump(),"status":"RUNNING"},10**9)
        (output/"tinyfish-browser-proof.json").write_text(json.dumps(proof,indent=2))
    try:
        openings=browser.find(lead,prefs,on_started=started)
        proof.update(status=browser.last_status,openings=[o.model_dump() for o in openings])
        ledger.cache(key,[o.model_dump() for o in openings],86400)
        ledger.delete_cache(pending_key)
        run=browser.get_run(browser.last_run_id)
        proof["reported_steps"]=run.get("num_of_steps")
    except ProviderError as exc:
        proof.update(status=exc.status,error=str(exc),run_id=exc.run_id or browser.last_run_id)
        ledger.cache(pending_key,{"run_id":proof.get("run_id"),"lead":lead.model_dump(),"status":exc.status},10**9)
        # Keep reservation/ID and recover later; never POST a second run.
    (output/"tinyfish-browser-proof.json").write_text(json.dumps(proof,indent=2))
    print(json.dumps(proof,indent=2))


if __name__=="__main__":main()
