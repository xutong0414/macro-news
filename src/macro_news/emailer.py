from __future__ import annotations

import smtplib
from email.message import EmailMessage
from pathlib import Path

from .config import Settings


def send_email(settings: Settings, subject: str, text_body: str, html_body: str, chart_path: Path | None = None) -> None:
    missing = settings.missing_for_send()
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Missing required email environment variables: {joined}")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.brief_from_email or settings.smtp_user or ""
    message["To"] = settings.brief_to_email or ""
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    if chart_path and chart_path.exists():
        message.add_attachment(
            chart_path.read_bytes(),
            maintype="image",
            subtype="png",
            filename=chart_path.name,
        )

    try:
        with smtplib.SMTP(settings.smtp_host or "", settings.smtp_port) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_user or "", settings.smtp_password or "")
            smtp.send_message(message)
    except smtplib.SMTPAuthenticationError as exc:
        raise RuntimeError(
            "SMTP authentication failed. For Gmail, use a 16-character app password "
            "created under Google Account > Security > 2-Step Verification > App passwords; "
            "do not use your normal Google login password."
        ) from exc
