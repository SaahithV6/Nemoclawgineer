from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from openclaw_engineering.config import get_settings


def _cache_root() -> Path:
    p = get_settings().data_dir / "mesh_cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


def mesh_key(stl_path: Path, size_mm: float) -> str:
    h = hashlib.sha256()
    h.update(stl_path.read_bytes() if stl_path.exists() else b"")
    h.update(str(size_mm).encode())
    return h.hexdigest()[:24]


def get_cached_inp(stl_path: Path, size_mm: float) -> Path | None:
    key = mesh_key(stl_path, size_mm)
    cached = _cache_root() / key / "model.inp"
    return cached if cached.exists() else None


def store_cached_inp(stl_path: Path, size_mm: float, inp_path: Path) -> Path:
    key = mesh_key(stl_path, size_mm)
    dest_dir = _cache_root() / key
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "model.inp"
    shutil.copy2(inp_path, dest)
    meta = {"stl": str(stl_path), "size_mm": size_mm}
    (dest_dir / "meta.json").write_text(json.dumps(meta))
    return dest
