from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import Session

from munim.modules.auth.dependencies import get_current_merchant_id
from munim.modules.records.schemas import (
    RecordDetail,
    RecordsListResponse,
)
from munim.modules.records.service import get_record, list_records
from munim.shared.db import get_session
from munim.shared.responses import SuccessEnvelope

router = APIRouter(prefix="/records", tags=["records"])


@router.get("", response_model=SuccessEnvelope[RecordsListResponse])
def list_endpoint(
    request: Request,
    source_system: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=200),
    merchant_id: str = Depends(get_current_merchant_id),
    session: Session = Depends(get_session),
) -> SuccessEnvelope[RecordsListResponse]:
    data = list_records(
        session,
        merchant_id,
        source_system=source_system,
        entity_type=entity_type,
        limit=limit,
    )
    return SuccessEnvelope(data=data, trace_id=request.state.trace_id)


@router.get("/{record_id}", response_model=SuccessEnvelope[RecordDetail])
def detail_endpoint(
    record_id: int,
    request: Request,
    merchant_id: str = Depends(get_current_merchant_id),
    session: Session = Depends(get_session),
) -> SuccessEnvelope[RecordDetail]:
    record = get_record(session, merchant_id, record_id)
    return SuccessEnvelope(data=record, trace_id=request.state.trace_id)
