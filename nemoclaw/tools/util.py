from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from nemoclaw.config import get_settings, load_defaults


def dry_run() -> bool:
    return get_settings().nemoclaw_dry_run


def which(cmd: str) -> str | None:
    return shutil.which(cmd)


def run_cmd(
    args: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        args,
        cwd=cwd,
        env=merged,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def ccx_threads() -> int:
    return int(load_defaults().get("resources", {}).get("ccx_threads", 16))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
