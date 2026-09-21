from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_current_user
from app.core.security import UserContext
from app.memory.document_store import get_company_evidence
from app.schemas.evidence import Evidence, EvidenceListResponse

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/{company_id}/evidence", response_model=EvidenceListResponse)
async def get_company_evidence_records(
    company_id: str,
    user: UserContext = Depends(get_current_user),
) -> EvidenceListResponse:
    records = await get_company_evidence(company_id=company_id)
    return EvidenceListResponse(
        company_id=company_id,
        total=len(records),
        evidence=[Evidence(**rec) for rec in records],
    )
