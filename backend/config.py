from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

# Render sets PORT; local dev uses LINK_VAULT_PORT.
PORT = int(os.getenv("PORT", os.getenv("LINK_VAULT_PORT", "8787")))
_default_host = "0.0.0.0" if os.getenv("PORT") or os.getenv("RENDER") else "127.0.0.1"
HOST = os.getenv("LINK_VAULT_HOST", _default_host)


def _resolve_db_path() -> Path:
    raw = os.getenv("LINK_VAULT_DB", str(ROOT / "data" / "link_vault.db"))
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    for candidate in (path, ROOT / "data" / "link_vault.db"):
        try:
            candidate.parent.mkdir(parents=True, exist_ok=True)
            probe = candidate.parent / ".write_probe"
            probe.write_text("1", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return candidate
        except OSError:
            continue
    return ROOT / "data" / "link_vault.db"


DB_PATH = _resolve_db_path()

# Required on public deploy; leave empty for trusted local-only use.
API_KEY = os.getenv("LINK_VAULT_API_KEY", "").strip()
PUBLIC_BASE_URL = os.getenv("LINK_VAULT_PUBLIC_URL", "").strip()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").strip()
LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("LLM_MODEL_API_KEY", "")).strip()
LLM_MODEL = os.getenv("LLM_MODEL", "GPT-oss-20B")
LLM_USER = os.getenv("LLM_USER", os.getenv("USER", "")).strip()

from .buckets import CANONICAL_BUCKETS  # noqa: F401 — re-export for API/features
