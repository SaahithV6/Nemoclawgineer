from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULTS_PATH = REPO_ROOT / "config" / "openclaw-engineering.defaults.yaml"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.expanduser("~/.openclaw-engineering/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openclaw_gateway_url: str = "http://localhost:3000"
    openclaw_api_token: str = ""
    openclaw_model: str = "nvidia/nemotron-3-super-120b-a12b"

    onshape_access_key: str = ""
    onshape_secret_key: str = ""
    onshape_base_url: str = "https://cad.onshape.com"
    onshape_document_id: str = ""
    onshape_workspace_id: str = ""
    onshape_element_id: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "openclaw_engineering@localhost"
    openclaw_engineering_notify_email: str = ""

    openclaw_engineering_data_dir: str = os.path.expanduser("~/.local/state/openclaw-engineering")
    openclaw_engineering_api_host: str = "127.0.0.1"
    openclaw_engineering_api_port: int = 8765
    openclaw_engineering_dry_run: bool = False
    openclaw_engineering_optuna_trials: int = 12
    openclaw_engineering_freecad_appimage: str = os.path.expanduser(
        "~/.local/share/openclaw-engineering/apps/FreeCAD.AppImage"
    )

    @property
    def data_dir(self) -> Path:
        return Path(os.path.expanduser(self.openclaw_engineering_data_dir))

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"

    @property
    def api_base(self) -> str:
        return f"http://{self.openclaw_engineering_api_host}:{self.openclaw_engineering_api_port}"

    @property
    def onshape_configured(self) -> bool:
        return bool(self.onshape_access_key and self.onshape_secret_key)


@lru_cache
def get_settings() -> Settings:
    dry = os.environ.get("OPENCLAW_ENGINEERING_DRY_RUN", os.environ.get("NEMCLAW_DRY_RUN", "0"))
    s = Settings()
    if dry in ("1", "true", "yes"):
        s.openclaw_engineering_dry_run = True
    return s


@lru_cache
def load_defaults() -> dict[str, Any]:
    if not DEFAULTS_PATH.exists():
        return {}
    with DEFAULTS_PATH.open() as f:
        return yaml.safe_load(f) or {}
