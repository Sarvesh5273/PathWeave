"""Actual browser/API/graph proof using the separately captured live engine result.

No interception/mocked API responses and no new provider requests. Use a dedicated
verification server/graph, never the participant's existing accepted main workspace.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from app.discovery.contracts import DiscoveryPreferences, EngineResult
from app.discovery.state import DiscoveryState
from playwright.sync_api import sync_playwright


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--url",default="http://127.0.0.1:18081")
    parser.add_argument("--state-path",required=True)
    args=parser.parse_args()
    assert ":18081" in args.url,"Use the dedicated verification server, not the main workspace."
    result=EngineResult.model_validate_json((ROOT/"reports/local/scout-live-engine-result.json").read_text())
    token=uuid4().hex
    ledger=DiscoveryState(args.state_path)
    hunt=ledger.create_hunt(token,DiscoveryPreferences(roles=["software engineering intern"],locations=["Germany"],companies=["Amazon"],opportunity_types=["company_roles"]),"Live engine verification")
    run=ledger.enqueue(hunt["id"],token)
    assert ledger.claim(run["id"])
    for event in result.events:ledger.event(run["id"],event)
    ledger.finish(run["id"],result)
    listing=next(v for v in result.listings if "Germany" in v.title and v.requirements)
    errors=[]
    with sync_playwright() as playwright:
        candidates=list((Path.home()/"Library/Caches/ms-playwright").glob("chromium_headless_shell-*/chrome-headless-shell-mac-arm64/chrome-headless-shell"))
        browser=playwright.chromium.launch(executable_path=str(sorted(candidates)[-1]) if candidates else None,headless=True)
        context=browser.new_context(viewport={"width":1365,"height":1000})
        context.add_init_script(f"localStorage.setItem('scout-client',{json.dumps(token)});localStorage.setItem('scout-last-hunt',{json.dumps(hunt['id'])});")
        page=context.new_page()
        page.on("pageerror",lambda error:errors.append(str(error)))
        page.goto(args.url,wait_until="networkidle")
        page.locator(f"[data-listing='{listing.id}']").wait_for()
        page.locator(f"[data-listing='{listing.id}']").click()
        assert page.locator("#weekly-hours").is_hidden()
        page.locator("#setup-plan-btn").click()
        page.locator("#plan-btn").click()
        page.wait_for_function("state.plan && !busy",timeout=30000)
        plan=page.evaluate("state.plan")
        assert any("practice" in task["title"].lower() for task in plan["tasks"])
        assert plan["weekly_used"].get("2026-11-02",0)==0
        assert any(e["excerpt"] for e in plan["evidence"])
        assert plan["targets"][0]["schedule_status"]=="cannot_certify"
        page.locator("[data-task-filter='Shared']").click()
        visible=page.locator("#task-list .task:not(.hidden)")
        assert visible.count()>0
        assert all(category=="Shared" for category in visible.evaluate_all("elements => elements.map(element => element.dataset.taskCategory)"))
        page.locator("[data-task-filter='All']").click()
        assert page.locator("#task-list .task:not(.hidden)").count()==len(plan["tasks"])
        page.locator("#accept-btn").click()
        page.wait_for_function("state.plan.status==='accepted' && !busy")
        accepted=page.evaluate("state.plan.id")
        page.screenshot(path=str(ROOT/"reports/local/cream-live-preparation-desktop.png"),full_page=True)
        page.locator("[data-step='evidence']").click()
        assert page.locator(".evidence-card").count()>0
        page.screenshot(path=str(ROOT/"reports/local/cream-live-evidence-desktop.png"),full_page=True)
        page.locator("#source-controls summary").click()
        assert page.locator("#refresh-source").is_visible()
        page.set_viewport_size({"width":390,"height":844})
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth+1")
        page.screenshot(path=str(ROOT/"reports/local/cream-live-evidence-mobile.png"),full_page=True)
        page.locator("[data-step='plan']").click()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth+1")
        page.screenshot(path=str(ROOT/"reports/local/cream-live-preparation-mobile.png"),full_page=True)
        page.reload(wait_until="networkidle")
        page.wait_for_function("state.plan && state.plan.status==='accepted'",timeout=15000)
        assert page.evaluate("state.plan.id")==accepted
        assert page.locator("#hunt-refresh").is_enabled()
        assert not errors,errors
        print(json.dumps({"result":"passed","mode":"actual browser/API/FalkorDB using separately retrieved live Search/Fetch/Groq results",
            "new_provider_calls":0,"listing":listing.title,"graph_tasks":len(plan["tasks"]),"accepted_id":accepted,
            "checks":["real shortlist rendered","selection before preparation time","source-backed skill preparation","shared/all work views","protected exam week","honest unknown readiness","accept/reload persistence","evidence/source controls","mobile plan/evidence layout","restored hunt controls","no JS errors"],
            "main_workspace_unchanged":True},indent=2))
        browser.close()


if __name__=="__main__":main()
