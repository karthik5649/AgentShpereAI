import logging
from typing import Any, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.dependencies import get_current_user
from app.core.security import UserContext
from app.services.eval_service import evaluate_dataset

logger = logging.getLogger("agentsphere.eval")

router = APIRouter(prefix="/eval", tags=["evaluation"])


class EvalRunRequest(BaseModel):
    companies: Optional[list[dict[str, Any]]] = None
    icp: Optional[dict[str, Any]] = None
    weights: Optional[dict[str, float]] = None
    cutoff: Optional[float] = None


@router.post("/run")
async def run_evaluation(
    payload: EvalRunRequest = EvalRunRequest(),
    user: UserContext = Depends(get_current_user),
) -> dict[str, Any]:
    return evaluate_dataset(
        companies=payload.companies,
        icp=payload.icp,
        weights=payload.weights,
        cutoff=payload.cutoff,
    )
