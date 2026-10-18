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
    discovery_state_path: str = os.getenv("DISCOVERY_STATE_PATH", str(ROOT / "data/runtime/scout.sqlite3"))
    discovery_daily_ai_calls: int = int(os.getenv("DISCOVERY_DAILY_AI_CALLS", "300"))
    discovery_daily_fetch_urls: int = int(os.getenv("DISCOVERY_DAILY_FETCH_URLS", "900"))
    discovery_daily_searches: int = int(os.getenv("DISCOVERY_DAILY_SEARCHES", "300"))
    discovery_ai_tpm: int = int(os.getenv("DISCOVERY_AI_TPM", "8000"))
    discovery_ai_max_output_tokens: int = int(os.getenv("DISCOVERY_AI_MAX_OUTPUT_TOKENS", "900"))
    discovery_ai_output_tpm: int = int(os.getenv("DISCOVERY_AI_OUTPUT_TPM", "1000"))
    discovery_ai_max_wait_seconds: float = float(os.getenv("DISCOVERY_AI_MAX_WAIT_SECONDS", "65"))
    discovery_ai_page_chars: int = int(os.getenv("DISCOVERY_AI_PAGE_CHARS", "7000"))
    tinyfish_agent_enabled: bool = os.getenv("TINYFISH_AGENT_ENABLED", "false").lower() == "true"
    tinyfish_agent_max_steps: int = int(os.getenv("TINYFISH_AGENT_MAX_STEPS", "0"))
    tinyfish_agent_step_cap_verified: bool = os.getenv("TINYFISH_AGENT_STEP_CAP_VERIFIED", "false").lower() == "true"
    discovery_agent_budget_usd: float = float(os.getenv("DISCOVERY_AGENT_BUDGET_USD", "0"))
    discovery_refresh_enabled: bool = os.getenv("DISCOVERY_REFRESH_ENABLED", "false").lower() == "true"
    discovery_basic_seconds: int = int(os.getenv("DISCOVERY_BASIC_SECONDS", "90"))
    tinyfish_agent_default_cap_verified: bool = os.getenv("TINYFISH_AGENT_DEFAULT_CAP_VERIFIED", "false").lower() == "true"
    tinyfish_agent_step_cost_usd: float = float(os.getenv("TINYFISH_AGENT_STEP_COST_USD", "0.016"))
    demo_tools_enabled: bool = os.getenv("ENABLE_DEMO_TOOLS", "false").lower() == "true"
    discovery_enrichment_seconds: int = int(os.getenv("DISCOVERY_ENRICHMENT_SECONDS", "150"))
    discovery_enrichment_pages: int = int(os.getenv("DISCOVERY_ENRICHMENT_PAGES", "6"))


settings = Settings()
