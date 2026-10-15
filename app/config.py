from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)


@dataclass(frozen=True)
class Settings:
    db_host: str = os.getenv("FALKORDB_HOST", "127.0.0.1")
    db_port: int = int(os.getenv("FALKORDB_PORT", "16379"))
    db_graph: str = os.getenv("FALKORDB_GRAPH", "just_chill_demo")
    db_password: str | None = os.getenv("FALKORDB_PASSWORD") or None
    db_ssl: bool = os.getenv("FALKORDB_SSL", "false").lower() == "true"
    groq_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
    tinyfish_key: str = os.getenv("TINYFISH_API_KEY", "")
    query_timeout_ms: int = 3000


settings = Settings()

