from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import settings
from app.graph import GraphStore
from app.models import ProfileState
from app.planner import build_plan


def main() -> None:
    db = GraphStore(settings)
    context = db.context(["epfl-summer-2027", "oist-fall-2027"])
    plan = db.save_plan(build_plan(context, ProfileState(completed_task_ids=["shared/cv-base/v1"])))
    accepted = db.accept_plan(plan.id)
    subprocess.run(["docker", "compose", "restart", "falkordb"], cwd=ROOT, check=True, capture_output=True)
    fresh = GraphStore(settings)
    for _ in range(20):
        if fresh.health().get("status") == "ok":
            break
        time.sleep(0.5)
    recovered = fresh.get_plan(accepted.id)
    assert recovered and recovered.status == "accepted"
    assert recovered.fact_versions == accepted.fact_versions
    assert next(t for t in recovered.tasks if t.task_id == "shared/cv-base/v1").status == "completed"
    output = {"database_restart": "passed", "accepted_plan": recovered.id,
              "completed_work": "preserved", "fact_versions": len(recovered.fact_versions),
              "graph": settings.db_graph}
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

