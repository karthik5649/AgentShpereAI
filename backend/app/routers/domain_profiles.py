import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_current_user
from app.core.security import UserContext
from app.domain.domain_profile import DomainProfile
from app.memory.document_store import (
    get_domain_profile,
    list_domain_profiles,
    save_domain_profile,
)

logger = logging.getLogger("agentsphere.domain_profiles")

router = APIRouter(prefix="/domain-profiles", tags=["domain-profiles"])


@router.get("", response_model=list[DomainProfile])
async def list_profiles(
    user: UserContext = Depends(get_current_user),
) -> list[DomainProfile]:
    profiles = await list_domain_profiles()
    return [DomainProfile(**p) for p in profiles]


@router.get("/{profile_id}", response_model=DomainProfile)
async def get_profile(
    profile_id: str,
    user: UserContext = Depends(get_current_user),
) -> DomainProfile:
    profile = await get_domain_profile(profile_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain profile '{profile_id}' not found",
        )
    return DomainProfile(**profile)


@router.post("", response_model=DomainProfile, status_code=status.HTTP_201_CREATED)
async def create_profile(
    payload: DomainProfile,
    user: UserContext = Depends(get_current_user),
) -> DomainProfile:
    doc = payload.model_dump()
    profile_id = await save_domain_profile(doc)
    saved = await get_domain_profile(profile_id)
    return DomainProfile(**saved)
