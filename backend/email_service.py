"""
Plug-and-Play Email Service
===========================
Swap email providers by changing EMAIL_PROVIDER in .env.
Supported: resend, sendgrid, brevo, smtp, mailgun
Add your own by implementing the BaseEmailProvider interface.

.env config:
  EMAIL_PROVIDER=resend          # resend | sendgrid | brevo | smtp | mailgun
  EMAIL_API_KEY=your_key_here    # API key for the chosen provider
  SENDER_EMAIL=you@yourdomain.com
  # SMTP-only extras:
  SMTP_HOST=smtp.gmail.com
  SMTP_PORT=587
  SMTP_USER=you@gmail.com
  SMTP_PASSWORD=app_password
"""

import os
import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class BaseEmailProvider(ABC):
    """Interface all email providers must implement."""

    @abstractmethod
    async def send(self, to: str, subject: str, html: str, sender: str) -> bool:
        ...


class ResendProvider(BaseEmailProvider):
    async def send(self, to, subject, html, sender):
        import resend
        resend.api_key = os.environ["EMAIL_API_KEY"]
        await asyncio.to_thread(resend.Emails.send, {
            "from": sender, "to": [to], "subject": subject, "html": html
        })
        return True


class SendGridProvider(BaseEmailProvider):
    async def send(self, to, subject, html, sender):
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {os.environ['EMAIL_API_KEY']}",
                    "Content-Type": "application/json"
                },
                json={
                    "personalizations": [{"to": [{"email": to}]}],
                    "from": {"email": sender},
                    "subject": subject,
                    "content": [{"type": "text/html", "value": html}]
                }
            )
            resp.raise_for_status()
        return True


class BrevoProvider(BaseEmailProvider):
    async def send(self, to, subject, html, sender):
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={
                    "api-key": os.environ["EMAIL_API_KEY"],
                    "Content-Type": "application/json"
                },
                json={
                    "sender": {"email": sender},
                    "to": [{"email": to}],
                    "subject": subject,
                    "htmlContent": html
                }
            )
            resp.raise_for_status()
        return True


class MailgunProvider(BaseEmailProvider):
    async def send(self, to, subject, html, sender):
        import httpx
        domain = os.environ.get("MAILGUN_DOMAIN", "")
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.mailgun.net/v3/{domain}/messages",
                auth=("api", os.environ["EMAIL_API_KEY"]),
                data={"from": sender, "to": [to], "subject": subject, "html": html}
            )
            resp.raise_for_status()
        return True


class SMTPProvider(BaseEmailProvider):
    async def send(self, to, subject, html, sender):
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to
        msg.attach(MIMEText(html, "html"))

        host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
        port = int(os.environ.get("SMTP_PORT", "587"))
        user = os.environ.get("SMTP_USER", sender)
        password = os.environ.get("SMTP_PASSWORD", "")

        def _send():
            with smtplib.SMTP(host, port) as server:
                server.starttls()
                server.login(user, password)
                server.sendmail(sender, to, msg.as_string())

        await asyncio.to_thread(_send)
        return True


# ── Provider registry ──
PROVIDERS = {
    "resend": ResendProvider,
    "sendgrid": SendGridProvider,
    "brevo": BrevoProvider,
    "mailgun": MailgunProvider,
    "smtp": SMTPProvider,
}


def get_email_provider() -> Optional[BaseEmailProvider]:
    """Return configured provider or None if not configured."""
    provider_name = os.environ.get("EMAIL_PROVIDER", "").lower().strip()
    api_key = os.environ.get("EMAIL_API_KEY", "").strip()

    if not provider_name:
        return None
    if provider_name != "smtp" and not api_key:
        return None
    if provider_name not in PROVIDERS:
        logger.warning(f"Unknown EMAIL_PROVIDER: {provider_name}. Options: {', '.join(PROVIDERS.keys())}")
        return None

    return PROVIDERS[provider_name]()


async def send_email(to: str, subject: str, html: str, sender: str = None) -> bool:
    """
    Send an email using the configured provider.
    Returns True on success, False if skipped/failed.
    """
    sender = sender or os.environ.get("SENDER_EMAIL", "noreply@whiskedwords.com")
    provider = get_email_provider()

    if not provider:
        logger.info(f"Email skipped (no provider configured): {subject} -> {to}")
        return False

    try:
        await provider.send(to, subject, html, sender)
        logger.info(f"Email sent via {os.environ.get('EMAIL_PROVIDER')}: {subject} -> {to}")
        return True
    except Exception as e:
        logger.error(f"Email failed via {os.environ.get('EMAIL_PROVIDER')}: {e}")
        return False
