from __future__ import annotations

import json
from pathlib import Path

import httpx

from openclaw_engineering.config import get_settings
from openclaw_engineering.store import artifact_path, job_dir


def write_delivery_manifest(job_id: str, notify_email: str | None, discord_user_id: str | None) -> Path:
    """Manifest for OpenClaw agent to attach files via Gmail/Discord skills."""
    d = job_dir(job_id)
    manifest = {
        "job_id": job_id,
        "notify_email": notify_email,
        "discord_user_id": discord_user_id,
        "artifacts": {
            "report": str(artifact_path(job_id, "REPORT.md")),
            "stl": str(artifact_path(job_id, "result.stl")),
            "metrics": str(artifact_path(job_id, "metrics.json")),
        },
        "instructions": (
            "Deliver REPORT.md and result.stl to the user via OpenClaw Gmail integration "
            "and confirm in Discord DM. Do not use raw SMTP passwords."
        ),
    }
    p = d / "DELIVERY.json"
    p.write_text(json.dumps(manifest, indent=2))
    return p


def notify_openclaw_agent(
    job_id: str,
    user_request: str,
    notify_email: str | None = None,
    discord_user_id: str | None = None,
) -> dict:
    """
    POST to OpenClaw /hooks/agent so Nemotron delivers results on Discord/Gmail.
    Requires hooks.enabled in ~/.openclaw/openclaw.json and OPENCLAW_HOOK_TOKEN.
    """
    s = get_settings()
    manifest = write_delivery_manifest(job_id, notify_email, discord_user_id)
    report = artifact_path(job_id, "REPORT.md")
    summary = report.read_text(errors="ignore")[:4000] if report.exists() else ""

    hook_token = _hook_token()
    if not hook_token:
        return {"status": "skipped", "reason": "no OPENCLAW_HOOK_TOKEN", "manifest": str(manifest)}

    base = s.openclaw_gateway_url.rstrip("/")
    url = f"{base}/hooks/agent"
    message = (
        f"OpenClaw Engineering job `{job_id}` finished.\n\n"
        f"User request: {user_request}\n\n"
        f"Read delivery manifest: {manifest}\n"
        f"Attach artifacts to the user:\n"
        f"- REPORT.md, result.stl, metrics.json\n"
        f"Email: {notify_email or 'use default Gmail channel'}\n"
        f"Discord user: {discord_user_id or 'current DM session'}\n\n"
        f"Report excerpt:\n{summary[:2000]}"
    )
    payload = {
        "message": message,
        "name": "openclaw-engineering-complete",
        "deliver": True,
        "channel": "discord",
        "wakeMode": "now",
    }
    if discord_user_id:
        payload["to"] = discord_user_id

    try:
        resp = httpx.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {hook_token}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )
        return {"status": "sent", "http": resp.status_code, "body": resp.text[:500]}
    except Exception as exc:
        return {"status": "failed", "error": str(exc), "manifest": str(manifest)}


def _hook_token() -> str:
    import os

    return os.environ.get("OPENCLAW_HOOK_TOKEN", "") or os.environ.get("OPENCLAW_API_TOKEN", "")
