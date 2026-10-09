# ==============================================================================
# File: backend/app/api/v1/hazard_analysis.py
# Description: FastAPI routes for multi-tenant Hazard Logging, Risk Matrix scoring,
#              HFACS 7.0 Nanocode Tagging, and CAPA creation.
#
#              Security (item 1A.8): every route requires an authenticated
#              session (get_tenant_user) and derives the tenant from the
#              session claims. The caller-supplied X-Tenant-Id header is no
#              longer accepted — it let any caller write into an arbitrary
#              tenant. Cross-tenant roles without a tenant are rejected.
#
#              NOTE: this router is currently NOT mounted in
#              app/api/v1/router.py (see hazard_service.py:14). The fix
#              applies to the code regardless of mount status.
# ==============================================================================

from fastapi import APIRouter, Depends, status
from typing import Any, Dict

from app.middleware.auth import get_tenant_user
from app.schemas.hazard_rca import (
    HazardCreate,
    RCAFactorCreate,
    RiskAssessmentCreate,
    CAPACreate,
)
from app.services.hazard_service import HazardService

router = APIRouter(prefix="/hazards", tags=["Hazard & RCA Analysis"])


def get_hazard_service() -> HazardService:
    return HazardService()


def _actor(user: Dict[str, Any]) -> Dict[str, Any]:
    """Identity recorded against writes, derived from the authenticated session."""
    return {
        "email": user.get("email"),
        "uid": user.get("uid"),
        "role": user.get("role"),
        "department": user.get("department"),
    }


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_new_hazard(
    payload: HazardCreate,
    user: Dict[str, Any] = Depends(get_tenant_user),
    service: HazardService = Depends(get_hazard_service),
):
    """Creates a new tracked hazard in the caller's tenant safety registry."""
    tenant_id = user["tenant_id"]
    hazard_id = await service.create_hazard(tenant_id, payload.dict(), _actor(user))
    return {"status": "success", "hazard_id": hazard_id}


@router.post("/{hazard_id}/rca", response_model=dict, status_code=status.HTTP_201_CREATED)
async def attach_hfacs_rca(
    hazard_id: str,
    payload: RCAFactorCreate,
    user: Dict[str, Any] = Depends(get_tenant_user),
    service: HazardService = Depends(get_hazard_service),
):
    """Tags a specific DoD HFACS 7.0 nanocode factor to the hazard analysis."""
    factor_id = await service.add_rca_factor(user["tenant_id"], hazard_id, payload.dict())
    return {"status": "success", "factor_id": factor_id}


@router.post("/{hazard_id}/assessments", response_model=dict, status_code=status.HTTP_201_CREATED)
async def record_risk_matrix_assessment(
    hazard_id: str,
    payload: RiskAssessmentCreate,
    user: Dict[str, Any] = Depends(get_tenant_user),
    service: HazardService = Depends(get_hazard_service),
):
    """Records an ICAO 5x5 initial or residual safety risk matrix evaluation."""
    res = await service.record_assessment(
        user["tenant_id"], hazard_id, payload.dict(), user.get("email")
    )
    return {"status": "success", "assessment": res}


@router.post("/{hazard_id}/capas", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_hazard_capa(
    hazard_id: str,
    payload: CAPACreate,
    user: Dict[str, Any] = Depends(get_tenant_user),
    service: HazardService = Depends(get_hazard_service),
):
    """Assigns a corrective and preventive action mitigating the root cause."""
    capa_id = await service.add_capa(user["tenant_id"], hazard_id, payload.dict())
    return {"status": "success", "capa_id": capa_id}
