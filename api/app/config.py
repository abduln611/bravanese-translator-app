"""Settings, read from environment variables (see README for the full list)."""
import os
from dataclasses import dataclass
from pathlib import Path

# api/app/config.py -> repo root is two levels above api/
REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    anthropic_api_key: str | None
    anthropic_model: str
    max_tokens: int
    allowed_origins: list[str]
    max_input_chars: int


def get_settings() -> Settings:
    return Settings(
        data_dir=Path(os.getenv("DATA_DIR", REPO_ROOT)),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5"),
        max_tokens=int(os.getenv("MAX_TOKENS", "1000")),
        allowed_origins=[
            o.strip()
            for o in os.getenv(
                "ALLOWED_ORIGINS",
                "https://barawatranslate.netlify.app,http://localhost:8000,http://localhost:8081",
            ).split(",")
            if o.strip()
        ],
        max_input_chars=int(os.getenv("MAX_INPUT_CHARS", "500")),
    )
