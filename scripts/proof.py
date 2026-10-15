from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings
from app.sources import DiscoverService
from app.graph import GraphStore
from app.models import ProfileState
from app.planner import build_plan
from app.agent import run_agent


def main() -> None:
    db = GraphStore(settings)
    if db.health().get("status") != "ok":
        raise RuntimeError("FalkorDB must be running; no mock substituted.")
    service = DiscoverService(settings)
    result = service.load_examples()
    if result.errors:
        raise RuntimeError("Recorded source examples could not be loaded.")
    by_url = {s.url: s for s in result.snapshots}
    for opportunity in result.opportunities:
        existing = db.get_opportunity(opportunity.id)
        if existing is not None and existing.mode == "live":
            continue
        db.upsert_opportunity(opportunity, by_url.get(opportunity.source_url))
    selected = ["epfl-summer-2027", "oist-fall-2027"]
    profile = ProfileState(completed_task_ids=["shared/cv-base/v1"])
    context = db.context(selected)
    plan = db.save_plan(build_plan(context, profile))
    assert sum(t.task_id == "shared/cv-base/v1" for t in plan.tasks) == 1
    assert next(t for t in plan.tasks if t.task_id == "shared/cv-base/v1").status == "completed"
    assert any(t.waiting_for for t in plan.tasks if t.task_id.startswith("oist-fall-2027/"))
    assert not any(t.task_id.startswith("epfl-summer-2027/reference") for t in plan.tasks)
    for week in plan.profile.exam_weeks:
        assert plan.weekly_used.get(week, 0) == 0
    for value in plan.weekly_used.values():
        assert value <= profile.weekly_hours + 1e-6
    accepted = db.accept_plan(plan.id)
    assert accepted.status == "accepted"
    recovered = GraphStore(settings).get_plan(plan.id)
    assert recovered is not None and recovered.id == accepted.id and recovered.status == "accepted"
    report = {"database": db.health(), "plan_id": accepted.id,
              "source_mode": "cached official snapshots",
              "tasks": len(plan.tasks), "evidence_paths": len(plan.evidence),
              "targets": [{"id": t.target_id, "schedule": t.schedule_status,
                           "eligibility": t.eligibility} for t in plan.targets],
              "checks": ["shared_base_once", "completed_cv_preserved", "external_waiting",
                         "program_reference_exception", "exam_capacity", "accepted_state_recovered"],
              "warnings": plan.warnings,
              "not_checked": ["live_llm", "database_container_restart", "full_ui", "deployment"]}
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

