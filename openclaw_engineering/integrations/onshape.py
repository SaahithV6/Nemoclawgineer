from __future__ import annotations

import base64
import hashlib
import hmac
import time
import uuid
from email.utils import formatdate
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

from openclaw_engineering.config import get_settings
from openclaw_engineering.models import OnShapeRef


class OnShapeClient:
    """Minimal OnShape REST client (API keys + HMAC)."""

    def __init__(
        self,
        access_key: str | None = None,
        secret_key: str | None = None,
        base_url: str | None = None,
    ):
        s = get_settings()
        self.access_key = access_key or s.onshape_access_key
        self.secret_key = secret_key or s.onshape_secret_key
        self.base_url = (base_url or s.onshape_base_url).rstrip("/")
        self.api = f"{self.base_url}/api"

    @property
    def configured(self) -> bool:
        return bool(self.access_key and self.secret_key)

    def _sign(self, method: str, path: str, query: str = "", content_type: str = "application/json") -> dict[str, str]:
        date = formatdate(timeval=None, localtime=False, usegmt=True)
        nonce = uuid.uuid4().hex.lower()
        query_part = f"?{query}" if query else ""
        auth_string = f"{method}\n{nonce}\n{date}\n{content_type}\n{path}{query_part}\n"
        sig = base64.b64encode(
            hmac.new(
                self.secret_key.encode(),
                auth_string.encode(),
                hashlib.sha256,
            ).digest()
        ).decode()
        return {
            "Date": date,
            "On-Nonce": nonce,
            "Authorization": f"On {self.access_key}:HmacSHA256:{sig}",
            "Content-Type": content_type,
            "Accept": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
        content: bytes | None = None,
        content_type: str = "application/json",
        timeout: float = 120.0,
    ) -> httpx.Response:
        query = urlencode(params or {})
        api_path = f"/api{path}" if not path.startswith("/api") else path
        headers = self._sign(method, api_path, query, content_type)
        url = f"{self.base_url}{api_path}"
        if query:
            url = f"{url}?{query}"
        with httpx.Client(timeout=timeout) as client:
            return client.request(
                method,
                url,
                headers=headers,
                json=json_body if content is None else None,
                content=content,
            )

    def export_stl(self, ref: OnShapeRef, out_path: Path, units: str = "meter") -> Path:
        """Export Part Studio to STL via translation API."""
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if get_settings().openclaw_engineering_dry_run or not self.configured:
            if not out_path.exists():
                out_path.write_bytes(b"openclaw-engineering onshape dry-run stl placeholder")
            return out_path

        path = (
            f"/v9/partstudios/d/{ref.document_id}/w/{ref.workspace_id}/e/{ref.element_id}/stl"
        )
        resp = self._request(
            "GET",
            path,
            params={"mode": "text", "grouping": "true", "units": units},
            content_type="application/vnd.onshape.v1+octet-stream",
        )
        if resp.status_code != 200:
            raise RuntimeError(f"OnShape STL export failed: {resp.status_code} {resp.text[:500]}")
        out_path.write_bytes(resp.content)
        return out_path

    def upload_stl_replace(
        self,
        ref: OnShapeRef,
        stl_path: Path,
        filename: str | None = None,
    ) -> dict[str, Any]:
        """Upload STL to document via blob/translation (simplified path)."""
        if get_settings().openclaw_engineering_dry_run or not self.configured:
            return {"status": "dry_run", "filename": filename or stl_path.name}

        fname = filename or stl_path.name
        path = f"/v6/blobelements/d/{ref.document_id}/w/{ref.workspace_id}"
        content_type = "application/octet-stream"
        query = urlencode({"storeInDocument": "true"})
        api_path = f"/api{path}"
        headers = self._sign("POST", api_path, query, content_type)
        url = f"{self.base_url}{api_path}?{query}"
        with httpx.Client(timeout=300.0) as client:
            resp = client.post(
                url,
                headers=headers,
                content=stl_path.read_bytes(),
                params={"fileName": fname} if False else None,
            )
        if resp.status_code not in (200, 201):
            # Fallback: return metadata for manual upload in demo
            return {
                "status": "upload_failed",
                "http_status": resp.status_code,
                "detail": resp.text[:300],
                "local_stl": str(stl_path),
                "filename": fname,
            }
        return resp.json() if resp.text else {"status": "ok", "filename": fname}


def default_onshape_ref() -> OnShapeRef | None:
    s = get_settings()
    if not (s.onshape_document_id and s.onshape_workspace_id and s.onshape_element_id):
        return None
    return OnShapeRef(
        document_id=s.onshape_document_id,
        workspace_id=s.onshape_workspace_id,
        element_id=s.onshape_element_id,
    )


def pull_from_onshape(job_dir: Path, ref: OnShapeRef | None) -> Path | None:
    ref = ref or default_onshape_ref()
    if not ref:
        return None
    client = OnShapeClient()
    if not client.configured:
        return None
    out = job_dir / "input_onshape.stl"
    return client.export_stl(ref, out)


def push_to_onshape(stl_path: Path, ref: OnShapeRef | None, part_name: str | None = None) -> dict:
    ref = ref or default_onshape_ref()
    if not ref:
        return {"status": "skipped", "reason": "no onshape ref"}
    client = OnShapeClient()
    return client.upload_stl_replace(ref, stl_path, filename=part_name or stl_path.name)
