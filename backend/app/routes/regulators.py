# ============================================================================
# FILE: regulators.py
# PATH: backend/app/routes/regulators.py
# PURPOSE: State Regulator API. Enumerates State Regulators (CAAN for Nepal,
#          DGCA for India, ...) and their overseen operator tenants. Only
#          STATE_SMD / SUPER_ADMIN (cross-tenant roles) may read.
# ============================================================================

from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from app.middleware.auth import get_caan_user
from app.services.regulator_service import get_regulator, list_regulators

router = APIRouter()


def _envelope(data: Any) -> Dict[str, Any]:
    return {
        "status": "success",
        "timestamp": datetime.now(),
        "data": data,
    }


@router.get("", status_code=status.HTTP_200_OK)
async def list_regulators_endpoint(
    user: Dict[str, Any] = Depends(get_caan_user),
):
    """List every State Regulator (e.g. CAAN/Nepal, DGCA/India)."""
    try:
        regulators = list_regulators()
    except Exception as e:
        logger.warning(f"Failed to list regulators: {e}")
        raise HTTPException(status_code=500, detail="Failed to list regulators")
    return _envelope({"regulators": regulators})


@router.get("/{regulator_id}", status_code=status.HTTP_200_OK)
async def get_regulator_endpoint(
    regulator_id: str,
    user: Dict[str, Any] = Depends(get_caan_user),
):
    """One State Regulator with its overseen operators."""
    reg = get_regulator(regulator_id)
    if not reg:
        raise HTTPException(status_code=404, detail=f"Unknown regulator: {regulator_id}")
    return _envelope({"regulator": reg})
