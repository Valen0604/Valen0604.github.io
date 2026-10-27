"""
Settings. Everything the team is likely to change lives here or in `.env`.

Where the API key goes
----------------------
Copy `.env.example` to `.env` and paste the key after `ANTHROPIC_API_KEY=`.
`.env` is git-ignored. The key is read here and handed to the Claude client only.
It is never placed in the environment of the process that runs analysis code.

With no key the app still starts, in offline demo mode (see app/agent/offline.py).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

_PLACEHOLDERS = {"", "your-key-here", "sk-ant-...", "changeme"}


def _raw() -> dict[str, str]:
    """`.env` first, then real environment variables on top."""
    values = {k: v for k, v in dotenv_values(ENV_FILE).items() if v is not None}
    for key, value in os.environ.items():
        if key.startswith(("ANTHROPIC_", "ADS_")):
            values[key] = value
    return values


def _flag(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # --- Claude -----------------------------------------------------------
    api_key: str | None
    model: str
    effort: str            # low | medium | high | xhigh | max
    max_tokens: int        # cap on one model response, not a target
    max_tool_rounds: int   # tool-call rounds allowed per user message
    send_charts_to_model: bool
    show_thinking: bool

    # --- Analysis engine --------------------------------------------------
    code_timeout_s: int
    model_timeout_s: int
    max_upload_mb: int
    max_tool_output_chars: int

    # --- Server -----------------------------------------------------------
    host: str
    port: int
    workspace: Path

    # --- Pricing, US dollars per million tokens (for the cost estimate) ----
    price_input: float
    price_output: float
    price_cache_write: float
    price_cache_read: float

    @property
    def live(self) -> bool:
        """True when a key is configured, so the real agent can run."""
        return self.api_key is not None

    def public(self) -> dict:
        """What the front-end is allowed to know. Never includes the key."""
        return {
            "live": self.live,
            "model": self.model if self.live else "offline demo (no API key)",
            "effort": self.effort,
            "max_upload_mb": self.max_upload_mb,
            "env_file": str(ENV_FILE),
        }


def load_settings() -> Settings:
    raw = _raw()
    key = (raw.get("ANTHROPIC_API_KEY") or "").strip()
    api_key = None if key.lower() in _PLACEHOLDERS else key

    # Absolute, because the analysis worker changes its working directory to the session
    # folder and a relative path would stop meaning the same thing there.
    workspace = Path(raw.get("ADS_WORKSPACE") or ROOT / "workspace").resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    return Settings(
        api_key=api_key,
        model=raw.get("ADS_MODEL") or "claude-sonnet-5",
        effort=(raw.get("ADS_EFFORT") or "medium").lower(),
        max_tokens=int(raw.get("ADS_MAX_TOKENS") or 32000),
        max_tool_rounds=int(raw.get("ADS_MAX_TOOL_ROUNDS") or 15),
        send_charts_to_model=_flag(raw.get("ADS_SEND_CHARTS_TO_MODEL"), True),
        show_thinking=_flag(raw.get("ADS_SHOW_THINKING"), True),
        code_timeout_s=int(raw.get("ADS_CODE_TIMEOUT_S") or 90),
        model_timeout_s=int(raw.get("ADS_MODEL_TIMEOUT_S") or 420),
        max_upload_mb=int(raw.get("ADS_MAX_UPLOAD_MB") or 200),
        max_tool_output_chars=int(raw.get("ADS_MAX_TOOL_OUTPUT_CHARS") or 14000),
        host=raw.get("ADS_HOST") or "127.0.0.1",
        port=int(raw.get("ADS_PORT") or 8000),
        workspace=workspace,
        # Claude Sonnet 5 list prices. Cache writes cost 1.25x input, reads 0.1x.
        price_input=float(raw.get("ADS_PRICE_INPUT") or 2.00),
        price_output=float(raw.get("ADS_PRICE_OUTPUT") or 10.00),
        price_cache_write=float(raw.get("ADS_PRICE_CACHE_WRITE") or 2.50),
        price_cache_read=float(raw.get("ADS_PRICE_CACHE_READ") or 0.20),
    )


SETTINGS = load_settings()
