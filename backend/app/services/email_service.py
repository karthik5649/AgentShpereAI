import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from email.message import EmailMessage
import smtplib
from typing import Any
from uuid import uuid4

from app.core.config import get_settings
from app.services.mocks.mock_email_sender import MockEmailSender

logger = logging.getLogger("agentsphere.email")


class EmailSenderProvider(ABC):
    @abstractmethod
    async def send(
        self,
        to: str,
        subject: str,
        body: str,
        workflow_id: str,
        company_id: str | None = None,
        contact_id: str | None = None,
    ) -> dict[str, Any]:
        """Send an outreach email and return status metadata."""
        pass


class SMTPEmailSender(EmailSenderProvider):
    def __init__(
        self,
        host: str,
        port: int,
        user: str | None = None,
        password: str | None = None,
        from_address: str = "outreach@agentsphere.ai",
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.from_address = from_address

    async def send(
        self,
        to: str,
        subject: str,
        body: str,
        workflow_id: str,
        company_id: str | None = None,
        contact_id: str | None = None,
    ) -> dict[str, Any]:
        def _send_sync() -> str:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = self.from_address
            msg["To"] = to
            msg.set_content(body)

            msg_id = f"msg_smtp_{uuid4().hex[:12]}"
            msg["Message-ID"] = f"<{msg_id}@{self.host}>"

            with smtplib.SMTP(self.host, self.port, timeout=15) as server:
                if self.port in {587, 25}:
                    try:
                        server.starttls()
                    except smtplib.SMTPNotSupportedError:
                        pass
                if self.user and self.password:
                    server.login(self.user, self.password)
                server.send_message(msg)
            return msg_id

        message_id = await asyncio.to_thread(_send_sync)
        return {
            "status": "sent",
            "message_id": message_id,
            "sent_at": datetime.now(UTC).isoformat(),
            "recipient": to,
            "subject": subject,
        }


def get_email_sender() -> EmailSenderProvider:
    settings = get_settings()
    if settings.MOCK_MODE or settings.EMAIL_SENDER_PROVIDER.lower() != "smtp":
        return MockEmailSender()

    return SMTPEmailSender(
        host=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        user=settings.SMTP_USER,
        password=settings.SMTP_PASSWORD,
        from_address=settings.SMTP_FROM_ADDRESS,
    )
