"""Browser UI regression check with explicitly mocked discovery responses.

This verifies controls/state/layout, not live TinyFish or FalkorDB behavior. Run the
separate provider/graph proofs for those claims. Requires the optional Playwright tool.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--url",default="http://127.0.0.1:18081")
    args=parser.parse_args()
    listing={"id":"fixture-listing","title":"Software Engineer Intern","organization":"Example",
        "locations":["Germany"],"cycle":"2027","kind":"job","score":85,"summary":"Fixture posting for UI verification only.",
        "call_status":"unknown","visa_status":"unknown","funding_level":"paid","is_new":True,
        "deadline_text":None,"deadline_precision":"unknown","funding_note":"A monthly salary is offered.",
        "requirements":[{"name":"skills","kind":"requirement","status":"known","excerpt":"Python and algorithms required."}],
        "reasons":["Fixture advisory fit; no eligibility certification"],"apply_url":"https://careers.example.org/jobs/1001",
        "found_via":"search","checked_at":"2026-10-16T10:00:00Z","saved":False,"hidden":False}
    second={**listing,"id":"fixture-research","title":"Research Internship · UI fixture","organization":"Example Lab","kind":"program","score":72,"saved":False,"hidden":False}
    hunt={"id":"fixture-hunt","name":"UI fixture","preferences":{},"result":{"listings":[listing,second]}}
    run={"id":"fixture-run","hunt":hunt["id"],"status":"partial","events":[
        {"stage":"search","message":"Mocked successful search for UI verification."},
        {"stage":"fetch","message":"Read fixture pages."},
        {"stage":"extract","message":"Extracted fixture requirements."},
        {"stage":"match","message":"Heuristic ranking in this UI fixture."},
        {"stage":"warning","message":"Fixture quota limit; no provider request occurred."}],"error":None}
    requests=[]
    errors=[]
    with sync_playwright() as playwright:
        candidates=list((Path.home()/"Library/Caches/ms-playwright").glob("chromium_headless_shell-*/chrome-headless-shell-mac-arm64/chrome-headless-shell"))
        browser=playwright.chromium.launch(executable_path=str(sorted(candidates)[-1]) if candidates else None,headless=True)
        page=browser.new_page(viewport={"width":1365,"height":1000})
        page.on("pageerror",lambda exc:errors.append(str(exc)))
        def mocked(route):
            request=route.request
            path=request.url.split("/api/",1)[1]
            requests.append((request.method,path))
            if path=="hunts":
                body={"hunt":hunt,"run":run} if request.method=="POST" else {"hunts":[{"id":hunt["id"],"name":hunt["name"],"latest_run":run["id"]}]}
            elif path=="hunts/fixture-hunt":body=hunt
            elif path=="discovery-runs/fixture-run":body=run
            elif path.endswith("/flags"):
                flags=request.post_data_json;listing.update(flags);body=flags
            elif path=="plan/latest":body={"plan":None}
            elif path=="opportunities":body={"opportunities":[]}
            elif path=="health":body={"database":{"status":"ok"},"discovery":{"agent_enabled":False}}
            else:
                route.continue_();return
            route.fulfill(status=200,content_type="application/json",body=json.dumps(body))
        page.route("**/api/**",mocked)
        page.goto(args.url,wait_until="networkidle")
        output=Path("reports/local")
        output.mkdir(parents=True,exist_ok=True)
        assert page.locator("#search-form").is_hidden()
        assert page.locator("#weekly-hours").is_hidden()
        assert "Agent off" in page.locator("#agent-status").text_content()
        page.locator("[data-step='plan']").click()
        assert page.locator("#weekly-hours").is_hidden()
        assert "Select your targets" in page.locator("#plan-empty").inner_text()
        page.locator("#back-btn").click()
        page.screenshot(path=str(output/"cream-ui-start-desktop.png"),full_page=True)
        page.locator("#known-interests-btn").focus()
        page.keyboard.press("Enter")
        assert page.locator("#search-form").is_visible()
        assert not page.locator("#advanced-preferences").evaluate("element => element.open")
        page.locator("#advanced-preferences summary").click()
        page.locator("#search-companies").fill("Amazon")
        page.locator("#advanced-preferences summary").click()
        page.locator("#explore-btn").click()
        assert page.locator("#explore-btn").get_attribute("aria-expanded")=="true"
        page.locator("#explore-skip").click()
        assert page.locator("#interest-explorer").is_hidden()
        assert page.locator("#search-form").is_visible()
        page.locator("#explore-btn").click()
        page.locator("#explore-apply").click()
        assert "Choose an activity" in page.locator("#explore-note").inner_text()
        page.locator("#interest-cards input").first.check()
        page.screenshot(path=str(output/"cream-ui-explorer.png"),full_page=True)
        page.locator("#explore-apply").click()
        assert page.locator("#explore-btn").get_attribute("aria-expanded")=="false"
        assert "software engineering" in page.locator("#search-query").input_value()
        page.locator("#search-locations").fill("Germany")
        page.locator("#search-btn").click()
        page.locator("[data-listing='fixture-listing']").wait_for()
        page.wait_for_function("!busy")
        assert "with gaps" in page.locator("#run-progress-title").inner_text()
        assert page.locator("#discovery-trace").evaluate("element => element.open")
        assert page.locator("#run-stages .logged").count()==4
        assert not page.locator("#run-stages .current").count()
        page.evaluate("paintRun({id:'running-fixture',status:'running',events:[{stage:'search',message:'A mocked search event'}]})")
        assert page.locator("#run-stages .logged").count()==1
        assert page.locator("#run-stages .current").get_attribute("data-stage")=="search"
        page.evaluate("paintRun({id:'failed-fixture',status:'failed',events:[]})")
        assert "could not finish" in page.locator("#run-progress-title").inner_text()
        assert page.locator("#run-stages .logged").count()==0
        page.evaluate("paintRun("+json.dumps(run)+")")
        assert page.locator("#hunt-refresh").is_enabled()
        page.locator("[data-listing='fixture-listing']").click()
        assert page.locator("#setup-plan-btn").is_enabled()
        assert page.locator("#weekly-hours").is_hidden()
        assert "1 / 3" in page.locator("#selection-count").inner_text()
        page.locator("#setup-plan-btn").click()
        assert page.locator("#weekly-hours").is_visible()
        assert page.locator("#plan-btn").is_enabled()
        assert "1 selected target" in page.locator("#prep-selection-note").inner_text()
        page.screenshot(path=str(output/"cream-ui-preparation-setup.png"),full_page=True)
        page.locator("#back-btn").click()
        page.locator("[data-save='fixture-listing']").click()
        page.wait_for_function("!busy")
        assert listing["saved"] is True
        page.locator("#listing-view").select_option("saved")
        assert page.locator("[data-listing]").count()==1
        page.locator("#listing-view").select_option("visible")
        page.locator("#shortlist-filters summary").click()
        page.locator("#listing-text").fill("research")
        assert page.locator("[data-listing]").count()==1
        assert page.locator("[data-listing='fixture-research']").is_visible()
        page.locator("#listing-text").fill("")
        page.locator("#listing-score").select_option("80")
        assert page.locator("[data-listing]").count()==1
        page.locator("#listing-score").select_option("0")
        page.locator("#shortlist-filters summary").click()
        page.locator("#listing-sort").select_option("match")
        page.locator("[data-hide='fixture-research']").click()
        page.wait_for_function("!busy")
        assert page.locator("[data-listing]").count()==1
        page.locator("#listing-view").select_option("hidden")
        assert page.locator("[data-listing='fixture-research']").is_visible()
        page.locator("[data-hide='fixture-research']").click()
        page.wait_for_function("!busy")
        page.locator("#listing-view").select_option("visible")
        page.reload(wait_until="networkidle")
        page.locator("[data-listing='fixture-listing']").wait_for()
        assert page.locator("#hunt-refresh").is_enabled()
        assert page.locator("#hunt-select").input_value()==hunt["id"]
        assert "1 / 3" in page.locator("#selection-count").inner_text()
        assert "Software Engineer Intern" in page.locator("#opportunity-cards").inner_text()
        page.screenshot(path=str(output/"cream-ui-results-desktop.png"),full_page=True)
        page.set_viewport_size({"width":390,"height":844})
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth+1")
        page.screenshot(path=str(output/"cream-ui-results-mobile.png"),full_page=True)
        page.locator("#advanced-preferences summary").click()
        assert page.locator("#search-companies").is_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth+1")
        page.locator("#advanced-preferences summary").click()
        page.locator("#setup-plan-btn").click()
        assert page.locator("#weekly-hours").is_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth+1")
        page.set_viewport_size({"width":320,"height":740})
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth+1")
        assert not errors,errors
        print(json.dumps({"result":"passed","mode":"mocked discovery browser UI; not live provider proof",
            "checks":["keyboard entry choice","optional exploration and skip","collapsed advanced preferences","actual-event stages/partial/failed states","disabled Agent disclosure","ranked grid cards","selection before time settings","save/hide filters","refresh enabled","reload hunt/selection restoration","390px and 320px layouts","no page errors"],
            "requests":len(requests),"screenshots":str(output)},indent=2))
        browser.close()


if __name__=="__main__":main()
