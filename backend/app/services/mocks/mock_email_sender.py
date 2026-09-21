import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

logger = logging.getLogger("agentsphere.email")


class MockEmailSender:
    """Mock Email Sender that simulates successful email dispatch and logs outreach."""

    def __init__(self, **kwargs):
        pass

    async def send(
        self,
        to: str,
        subject: str,
        body: str,
        workflow_id: str,
        company_id: str | None = None,
        contact_id: str | None = None,
    ) -> dict[str, Any]:
        message_id = f"msg_mock_{uuid4().hex[:12]}"
        now = datetime.now(UTC).isoformat()
        logger.info(
            f"[MOCK EMAIL OUTREACH] To: {to} | Subject: {subject} | Contact: {contact_id} | MsgID: {message_id}"
        )
        return {
            "status": "sent",
            "message_id": message_id,
            "sent_at": now,
            "recipient": to,
            "subject": subject,
        }
