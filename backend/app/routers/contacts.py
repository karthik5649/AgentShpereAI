from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.dependencies import get_current_user
from app.core.security import UserContext
from app.memory.document_store import (
    get_contact,
    get_email_activities,
    get_workflow,
    record_email_activity,
)
from app.services.email_service import get_email_sender

router = APIRouter(prefix="/contacts", tags=["contacts"])


class SendEmailRequest(BaseModel):
    subject: str | None = None
    body: str | None = None


class SendEmailResponse(BaseModel):
    status: str
    message_id: str
    contact_id: str
    recipient: str
    timestamp: str


@router.post("/{contact_id}/send", response_model=SendEmailResponse)
async def send_contact_outreach(
    contact_id: str,
    payload: SendEmailRequest | None = None,
    user: UserContext = Depends(get_current_user),
) -> SendEmailResponse:
    contact = await get_contact(contact_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contact {contact_id} was not found",
        )

    # Hard requirement: Only approved contacts can receive outreach!
    if contact.get("approval_status") != "approved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Contact {contact_id} is '{contact.get('approval_status', 'unknown')}'. Outreach emails can only be sent to approved contacts.",
        )

    recipient = contact.get("email")
    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Contact {contact.get('name')} does not have a verified email address",
        )

    company_name = contact.get("company", "your team")
    workflow_id = contact.get("workflow_id", "")
    company_id = contact.get("company_id")

    # Generate or use provided subject and body
    subject = (payload and payload.subject) or f"Quick question regarding {company_name}"
    body = (payload and payload.body) or (
        f"Hi {contact.get('name', '').split(' ')[0]},\n\n"
        f"I noticed the exciting growth and recent milestones at {company_name}. "
        f"Given your leadership as {contact.get('title', 'leader')}, I wanted to share how "
        f"our platform helps teams scale revenue and operations seamlessly.\n\n"
        f"Would you be open to a brief 10-minute chat this week?\n\n"
        f"Best regards,\nAgentSphere Intelligence"
    )

    sender = get_email_sender()
    send_result = await sender.send(
        to=recipient,
        subject=subject,
        body=body,
        workflow_id=workflow_id,
        company_id=company_id,
        contact_id=contact_id,
    )

    activity_doc = {
        "workflow_id": workflow_id,
        "company_id": company_id,
        "contact_id": contact_id,
        "user_id": user.user_id,
        "recipient": recipient,
        "subject": subject,
        "body": body,
        "status": send_result.get("status", "sent"),
        "message_id": send_result.get("message_id"),
        "sent_at": send_result.get("sent_at") or datetime.now(UTC).isoformat(),
    }
    await record_email_activity(activity_doc)

    return SendEmailResponse(
        status="sent",
        message_id=send_result.get("message_id", ""),
        contact_id=contact_id,
        recipient=recipient,
        timestamp=activity_doc["sent_at"],
    )


@router.get("/{contact_id}/activities")
async def list_contact_activities(
    contact_id: str,
    user: UserContext = Depends(get_current_user),
) -> list[dict[str, Any]]:
    return await get_email_activities(contact_id=contact_id, user_id=user.user_id)
