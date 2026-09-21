import logging
from typing import Any
from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.core.security import UserContext
from app.memory.document_store import get_analytics_metrics

logger = logging.getLogger("agentsphere.analytics")

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("")
async def get_analytics(
    user: UserContext = Depends(get_current_user),
) -> dict[str, Any]:
    return await get_analytics_metrics(user.user_id)
