from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULTS_PATH = REPO_ROOT / "config" / "nemoclaw.defaults.yaml"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.expanduser("~/.nemoclaw/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    discord_bot_token: str = ""
    openclaw_gateway_url: str = "http://localhost:3000"
    openclaw_api_token: str = ""
    openclaw_model: str = "nvidia/nemotron-3-super-120b-a12b"
    nemoclaw_data_dir: str = os.path.expanduser("~/.local/state/nemoclaw")
    nemoclaw_api_host: str = "127.0.0.1"
    nemoclaw_api_port: int = 8765
    nemoclaw_dry_run: bool = False

    @property
    def data_dir(self) -> Path:
        return Path(os.path.expanduser(self.nemoclaw_data_dir))

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"

    @property
    def api_base(self) -> str:
        return f"http://{self.nemoclaw_api_host}:{self.nemoclaw_api_port}"


@lru_cache
def get_settings() -> Settings:
    dry = os.environ.get("NEMCLAW_DRY_RUN", "0")
    s = Settings()
    if dry in ("1", "true", "yes"):
        s.nemoclaw_dry_run = True
    return s


@lru_cache
def load_defaults() -> dict[str, Any]:
    if not DEFAULTS_PATH.exists():
        return {}
    with DEFAULTS_PATH.open() as f:
        return yaml.safe_load(f) or {}
