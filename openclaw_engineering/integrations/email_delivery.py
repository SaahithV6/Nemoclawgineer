from __future__ import annotations

import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from openclaw_engineering.config import get_settings


def send_job_results(
    to_addrs: str | list[str],
    subject: str,
    body_md: str,
    attachments: list[Path],
) -> None:
    s = get_settings()
    if isinstance(to_addrs, str):
        recipients = [a.strip() for a in to_addrs.split(",") if a.strip()]
    else:
        recipients = to_addrs
    if not recipients:
        raise ValueError("No email recipients")

    if s.openclaw_engineering_dry_run or not s.smtp_host:
        out = s.data_dir / "email_preview.eml"
        out.write_text(f"To: {recipients}\nSubject: {subject}\n\n{body_md}\n")
        return

    msg = MIMEMultipart()
    msg["From"] = s.smtp_from
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(body_md, "plain"))
    for path in attachments:
        if not path.exists():
            continue
        part = MIMEApplication(path.read_bytes(), Name=path.name)
        part["Content-Disposition"] = f'attachment; filename="{path.name}"'
        msg.attach(part)

    with smtplib.SMTP(s.smtp_host, s.smtp_port) as server:
        server.starttls()
        if s.smtp_user:
            server.login(s.smtp_user, s.smtp_password)
        server.sendmail(s.smtp_from, recipients, msg.as_string())
