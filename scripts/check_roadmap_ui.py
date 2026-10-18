"""Offline browser check for v0.7 timetable and roadmap controls.

API responses are intercepted fixtures: this makes no provider or graph write.
"""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    opportunity = {
        "id": "ui-target", "program": "UI Roadmap Internship", "cycle": "fixture",
        "category": "Company", "country": "Japan", "source_url": "https://example.org/job",
        "checked_at": "2026-10-18T00:00:00Z", "call_status": "open", "verification": "partial",
        "mode": "synthetic", "facts": [], "summary": "UI fixture", "discovery": {},
    }
    profile = {
        "id": "browser-fixture", "synthetic": False, "weekly_hours": 6,
        "start_date": "2026-10-19", "horizon_weeks": 3,
        "exam_weeks": ["2026-10-26"], "holidays": ["2026-10-23"],
        "weekly_pattern": {"0": 1, "2": 2, "5": 3}, "skill_ratings": {},
        "completed_task_ids": [], "received_events": [], "skills": {},
    }
    plan = {
        "id": "plan-ui-roadmap", "created_at": "2026-10-18T00:00:00Z",
        "selected_ids": ["ui-target"], "profile": profile, "targets": [], "tasks": [],
        "evidence": [], "fact_versions": {}, "total_hours_low": 2, "total_hours_high": 4,
        "available_hours": 12, "weekly_used": {"2026-10-19": 2, "2026-10-26": 0, "2026-11-02": 2},
        "status": "proposed", "next_action": "Start Python foundations.", "warnings": [],
        "affected_target_ids": [], "affected_task_ids": [],
        "roadmap": [
            {"key": "python", "title": "Python", "family": "Programming", "order": 1,
             "rating": "", "start_here": True, "prerequisites": [],
             "resources": [{"title": "Python tutorial", "url": "https://docs.python.org/3/tutorial/"}],
             "task_ids": ["shared/skill-python-foundation/v1"], "task_status": "scheduled",
             "required_by": {"ui-target": ["skills"]}, "scheduled": True, "note": ""},
            {"key": "machine_learning", "title": "Machine learning", "family": "Data & AI", "order": 2,
             "rating": "new", "start_here": False, "prerequisites": ["python"], "resources": [],
             "task_ids": [], "task_status": "", "required_by": {"ui-target": ["skills"]},
             "scheduled": False, "note": "Prerequisite guidance."},
        ],
    }
    errors: list[str] = []
    posts: list[dict] = []
    with sync_playwright() as playwright:
        candidates = list((Path.home() / "Library/Caches/ms-playwright").glob(
            "chromium_headless_shell-*/chrome-headless-shell-mac-arm64/chrome-headless-shell"))
        browser = playwright.chromium.launch(
            executable_path=str(sorted(candidates)[-1]) if candidates else None, headless=True)
        page = browser.new_page(viewport={"width": 1365, "height": 1000})
        page.on("pageerror", lambda exc: errors.append(str(exc)))

        def mocked(route):
            path = route.request.url.split("/api/", 1)[1]
            if path == "health":
                body = {"database": {"status": "ok"}, "discovery": {"agent_enabled": False}}
            elif path == "opportunities":
                body = {"opportunities": [opportunity]}
            elif path == "plan/latest":
                body = {"plan": plan}
            elif path == "hunts":
                body = {"hunts": []}
            elif path == "plan" and route.request.method == "POST":
                payload = route.request.post_data_json
                posts.append(payload)
                plan["profile"] = payload["profile"]
                for item in plan["roadmap"]:
                    item["rating"] = payload["profile"].get("skill_ratings", {}).get(item["key"], "")
                body = plan
            else:
                body = {}
            route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

        page.route("**/api/**", mocked)
        page.goto("http://127.0.0.1:18080", wait_until="networkidle")
        page.locator('[data-step="plan"]').click()
        assert page.locator("#roadmap-list .roadmap-item").count() == 2
        assert page.locator("#roadmap-list .start-badge").inner_text() == "START HERE"
        assert page.locator("#hours-0").input_value() == "1"
        assert page.locator("#exam-weeks-list .date-chip").count() == 1
        assert page.locator("#holidays-list .date-chip").count() == 1
        page.locator("#exam-week").fill("2026-11-05")
        page.locator("#exam-week-add").click()
        assert page.locator("#exam-weeks-list .date-chip").count() == 2
        page.locator('[data-rating="python"]').select_option("comfortable")
        page.wait_for_timeout(100)
        assert posts and posts[-1]["profile"]["skill_ratings"]["python"] == "comfortable"
        assert errors == [], errors
        browser.close()
    print("roadmap UI check passed: daily pattern, multiple calendar blocks, roadmap and rating replan")


if __name__ == "__main__":
    main()
