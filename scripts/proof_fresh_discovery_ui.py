"""A fresh user-style discovery run, not cached results or intercepted responses.

Exercises the actual browser -> queue -> Search/Fetch -> extraction/ranking flow on
a dedicated verification server. No main preparation mutations or automatic applications.
Do not repeatedly rerun on failure: preserve the report and investigate the specific gap.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
import sys

from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--url",default="http://127.0.0.1:18081")
    parser.add_argument("--roles",default="software engineering intern, robotics intern")
    parser.add_argument("--location",default="Japan")
    parser.add_argument("--minimum-listings",type=int,default=2)
    parser.add_argument("--state-path",help="Optional local verifier DB for retaining exact source snapshots/logs; never printed.")
    args=parser.parse_args()
    assert ":18081" in args.url,"Use the isolated verifier, not the main workspace."
    output=Path("reports/local")
    output.mkdir(parents=True,exist_ok=True)
    errors=[]
    with sync_playwright() as pw:
        candidates=list((Path.home()/"Library/Caches/ms-playwright").glob("chromium_headless_shell-*/chrome-headless-shell-mac-arm64/chrome-headless-shell"))
        browser=pw.chromium.launch(executable_path=str(sorted(candidates)[-1]) if candidates else None,headless=True)
        page=browser.new_page(viewport={"width":1365,"height":1000})
        page.on("pageerror",lambda error:errors.append(str(error)))
        started=time.monotonic()
        page.goto(args.url,wait_until="networkidle")
        page.locator("#known-interests-btn").click()
        page.locator("#search-query").fill(args.roles)
        page.locator("#search-locations").fill(args.location)
        page.locator("#search-btn").click()
        page.wait_for_function("state.hunt && document.querySelector('#run-progress').classList.contains('hidden')===false",timeout=15000)
        page.wait_for_function("!busy",timeout=330000)
        payload=page.evaluate("({hunt:state.hunt,listings:state.listings,notification:document.getElementById('notification').textContent,runStatus:document.getElementById('run-status-label').textContent})")
        report={"mode":"fresh browser initiated discovery; no mocks/no prefetched results", "seconds":round(time.monotonic()-started,2),
                "roles":args.roles,"location":args.location,"data":payload,"javascript_errors":errors}
        if args.state_path and payload.get("hunt"):
            from app.discovery.state import DiscoveryState
            token=page.evaluate("localStorage.getItem('scout-client')")
            report["server_hunt"]=DiscoveryState(args.state_path).hunt(payload["hunt"]["id"],token)
        (output/"fresh-discovery-browser-proof.json").write_text(json.dumps(report,indent=2))
        page.screenshot(path=str(output/"fresh-discovery-browser.png"),full_page=True)
        matches=[v for v in payload["listings"] if v.get('call_status')!='closed' and not v.get('summary','').startswith('INDEX SUMMARY')]
        assert len(matches)>=args.minimum_listings,f"Fresh hunt returned only {len(matches)} listing(s); see saved actual result/log."
        from app.discovery.ranking import place_matches
        relevant=[v for v in matches if v['score']>=60 and v.get('seniority')=='internship' and any(place_matches(args.location,location) for location in v['locations'])]
        assert relevant,"No reasonable-fit listing with source-supported requested location; foreign low-match cards are not success."
        assert payload['hunt']['result']['usage'].get('ai_attempts',0)==0,"Basic discovery must not call an LLM."
        assert not errors,errors
        saved=matches[0]
        page.locator(f"[data-save='{saved['id']}']").click()
        page.wait_for_function("!busy")
        page.reload(wait_until="networkidle")
        page.wait_for_function("state.hunt && state.listings.length>0",timeout=15000)
        assert page.evaluate("state.listings.some(listing => listing.saved)")
        print(json.dumps({"result":"passed","mode":report['mode'],"seconds":report['seconds'],
            "listings":len(matches),"summary":[{'title':v['title'],'organization':v['organization'],'location':v['locations'],'score':v['score'],'known_requirements':sum(f['status']=='known' for f in v.get('requirements',[]))} for v in matches],
            "run_status":payload['runStatus'],"save_reload":True,"agent_spend":"none requested by this proof","main_plan_unchanged":True},indent=2))
        browser.close()


if __name__=="__main__":main()
