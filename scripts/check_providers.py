from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx
from app.config import settings
from app.sources import DiscoverService


def main() -> None:
    report = {"configured": {"groq": bool(settings.groq_key), "tinyfish": bool(settings.tinyfish_key)}}
    if settings.groq_key:
        try:
            with httpx.Client(timeout=15) as client:
                response = client.get("https://api.groq.com/openai/v1/models",
                                      headers={"Authorization": f"Bearer {settings.groq_key}"})
            report["groq_status"] = response.status_code
            if response.status_code == 200:
                ids = {m["id"] for m in response.json().get("data", []) if isinstance(m, dict) and "id" in m}
                report["groq_model_available"] = settings.groq_model in ids
                report["groq_model"] = settings.groq_model
        except httpx.HTTPError:
            report["groq_error"] = "Provider unreachable."
    if settings.tinyfish_key:
        result = DiscoverService(settings).refresh("https://summer.epfl.ch/apply.html")
        report["tinyfish"] = {"mode": result.mode, "sources": len(result.snapshots),
                             "targets": [o.id for o in result.opportunities], "errors": result.errors}
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

