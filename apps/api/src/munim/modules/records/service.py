from sqlmodel import Session, col, select

from munim.models import Record
from munim.modules.records.schemas import (
    RecordDetail,
    RecordsListResponse,
    RecordSummary,
    clamp_limit,
)
from munim.shared.constants import ErrorCode
from munim.shared.errors import MunimError


class RecordNotFoundError(MunimError):
    code = ErrorCode.RECORD_NOT_FOUND.value
    http_status = 404
    message = "Record not found."


def list_records(
    session: Session,
    merchant_id: str,
    *,
    source_system: str | None,
    entity_type: str | None,
    limit: int,
) -> RecordsListResponse:
    effective_limit = clamp_limit(limit)
    stmt = (
        select(Record)
        .where(Record.merchant_id == merchant_id)
        .order_by(col(Record.fetched_at).desc())
        .limit(effective_limit)
    )
    if source_system:
        stmt = stmt.where(Record.source_system == source_system)
    if entity_type:
        stmt = stmt.where(Record.entity_type == entity_type)

    rows = session.exec(stmt).all()
    items = [
        RecordSummary(
            id=r.id if r.id is not None else 0,
            source_system=r.source_system,
            source_id=r.source_id,
            entity_type=r.entity_type,
            fetched_at=r.fetched_at,
        )
        for r in rows
    ]
    return RecordsListResponse(items=items, limit=effective_limit)


def get_record(
    session: Session,
    merchant_id: str,
    record_id: int,
) -> RecordDetail:
    row = session.exec(
        select(Record).where(Record.id == record_id).where(Record.merchant_id == merchant_id)
    ).first()
    if row is None:
        raise RecordNotFoundError(
            message=f"Record {record_id} not found for this merchant.",
            details={"record_id": record_id},
        )
    return RecordDetail(
        id=row.id if row.id is not None else 0,
        source_system=row.source_system,
        source_id=row.source_id,
        entity_type=row.entity_type,
        fetched_at=row.fetched_at,
        payload_hash=row.payload_hash,
        raw=row.raw,
        normalized=row.normalized,
    )
