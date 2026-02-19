"""Simple SMTP email sender."""

import logging
import smtplib
from collections.abc import Iterable
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger("medmemory.email")


def send_email(to_addresses: Iterable[str], subject: str, body: str) -> bool:
    if not settings.smtp_enabled:
        logger.info("SMTP disabled. Skipping email send.")
        return False
    if not settings.smtp_host or not settings.smtp_from:
        logger.warning("SMTP is enabled but host/from are not configured.")
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from
    message["To"] = ", ".join(to_addresses)
    message.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)
        return True
    except Exception:
        logger.exception("Failed to send email")
        return False
