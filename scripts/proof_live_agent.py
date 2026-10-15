from __future__ import annotations

import json
import sys
from pathlib import Path
from time import monotonic

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from app.main import app


def main() -> None:
    client = TestClient(app)
    started = monotonic()
    response = client.post("/api/agent", json={
        "selected_ids": ["epfl-summer-2027", "oist-fall-2027"],
        "profile": {"synthetic": True, "completed_task_ids": ["shared/cv-base/v1"]},
        "message": "Inspect the official requirements and propose my preparation plan. Explain the reference receipt blocker and the next useful action.",
    })
    result = response.json()
    if response.status_code != 200:
        print(json.dumps({"status": response.status_code, "detail": result.get("detail")}, indent=2))
        raise SystemExit(1)
    trace = result.get("trace", [])
    executed = [item["tool"] for item in trace if item.get("outcome") == "executed"]
    proposal = next((item["result"].get("plan") for item in reversed(result.get("results", []))
                     if item["result"].get("plan")), None)
    assert "inspect_requirements" in executed
    assert "propose_plan" in executed
    assert proposal and proposal["status"] == "proposed"
    assert any(task["waiting_for"] for task in proposal["tasks"])
    print(json.dumps({
        "status": response.status_code,
        "provider": result["provider"], "model": result["model"],
        "elapsed_seconds": round(monotonic() - started, 2),
        "executed_tools": executed,
        "trace": trace,
        "plan_id": proposal["id"],
        "next_action": proposal["next_action"],
        "message": result["message"],
        "usage": result.get("usage", []),
        "no_application_submission": True,
    }, indent=2))


if __name__ == "__main__":
    main()

