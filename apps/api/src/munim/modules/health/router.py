from fastapi import APIRouter, Request

from munim.modules.health.service import HealthData, check_health
from munim.shared.responses import SuccessEnvelope

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=SuccessEnvelope[HealthData])
def health(request: Request) -> SuccessEnvelope[HealthData]:
    return SuccessEnvelope(data=check_health(), trace_id=request.state.trace_id)
