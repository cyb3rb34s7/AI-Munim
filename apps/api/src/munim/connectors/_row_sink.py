"""The only thing that writes to the `record` table.

Connectors hand `RowSink.upsert(...)` a normalized Pydantic entity + the raw
source payload; the sink stamps provenance (merchant_id, source_system,
fetched_at, payload_hash) and upserts on the natural key
`(merchant_id, source_system, source_id)`.

`commit()` is the CALLER's responsibility - the sink uses `session.add` so a
batch of upserts can be wrapped in one transaction.
"""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from sqlmodel import Session, select

from munim.models import Record
from munim.shared.constants import EntityType, SourceSystem


class RowSink:
    def __init__(
        self,
        session: Session,
        merchant_id: str,
        source_system: SourceSystem,
    ) -> None:
        self._session = session
        self._merchant_id = merchant_id
        self._source_system = source_system

    def upsert(
        self,
        *,
        source_id: str,
        entity_type: EntityType,
        raw: dict[str, Any],
        normalized: BaseModel,
    ) -> tuple[Record, bool]:
        """Insert or update one row. Returns (record, was_changed).

        was_changed is True if the row was inserted or its payload_hash
        differed from the existing row; False if the existing row matched
        byte-for-byte and no update was needed.
        """
        payload_hash = _hash_payload(raw)
        normalized_json = normalized.model_dump(mode="json")

        existing = self._session.exec(
            select(Record).where(
                Record.merchant_id == self._merchant_id,
                Record.source_system == self._source_system.value,
                Record.source_id == source_id,
            )
        ).first()

        now = datetime.now(UTC)

        if existing is None:
            record = Record(
                merchant_id=self._merchant_id,
                source_system=self._source_system.value,
                source_id=source_id,
                entity_type=entity_type.value,
                fetched_at=now,
                payload_hash=payload_hash,
                raw=raw,
                normalized=normalized_json,
            )
            self._session.add(record)
            return record, True

        if existing.payload_hash == payload_hash:
            return existing, False

        existing.fetched_at = now
        existing.payload_hash = payload_hash
        existing.raw = raw
        existing.normalized = normalized_json
        self._session.add(existing)
        return existing, True


def _hash_payload(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
