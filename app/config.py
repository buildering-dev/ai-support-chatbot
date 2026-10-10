"""Settings, read from environment variables (or a .env file)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader so the project has no extra dependency for it."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


ROOT = Path(__file__).resolve().parent.parent
_load_dotenv(ROOT / ".env")


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


@dataclass
class Settings:
    business_name: str = os.getenv("BUSINESS_NAME", "Harbour Bikes (demo)")
    docs_dir: Path = Path(os.getenv("DOCS_DIR", str(ROOT / "data" / "sample_docs")))
    data_dir: Path = Path(os.getenv("DATA_DIR", str(ROOT / "data")))

    # LLM provider: "anthropic", "openai" (any OpenAI-compatible API: OpenAI,
    # OpenRouter, Groq, a local Ollama server...) or "offline" (no API key needed;
    # answers by quoting the best-matching passage).
    llm_provider: str = os.getenv("LLM_PROVIDER", "offline").lower()
    llm_model: str = os.getenv("LLM_MODEL", "")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    llm_timeout_s: float = _float("LLM_TIMEOUT_S", 30.0)

    # Retrieval and guardrails
    top_k: int = _int("TOP_K", 4)
    min_score: float = _float("MIN_SCORE", 1.0)  # below this, hand off to a human
    history_turns: int = _int("HISTORY_TURNS", 6)

    # Web server
    allowed_origins: list[str] = field(
        default_factory=lambda: [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
    )
    rate_limit_per_min: int = _int("RATE_LIMIT_PER_MIN", 20)

    # Telegram
    telegram_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")


settings = Settings()
