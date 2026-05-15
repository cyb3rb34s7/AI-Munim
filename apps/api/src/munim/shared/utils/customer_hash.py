"""Cross-connector customer identity hash.

A SHA-256-truncated digest of email (preferred) or phone (fallback) gives a
stable join key without storing PII. Same algorithm in every connector mapper
so the same human matches across sources (Shopify orders ↔ Shiprocket
shipments) for the RTO agent's customer-history signal.

Empty strings are normalised to None at entry so the two upstream conventions
("missing email is None" vs "missing email is empty string") produce identical
hashes for the same customer.
"""

import hashlib

from munim.shared.constants import ErrorCode
from munim.shared.errors import MunimError

_CUSTOMER_HASH_LENGTH = 16


class MissingCustomerIdentityError(MunimError):
    code = ErrorCode.VALIDATION_MISSING_FIELD.value
    http_status = 422
    message = "Cannot compute customer_source_id: neither email nor phone present."


def compute_customer_source_id(email: str | None, phone: str | None) -> str:
    normalised_email = (email or "").strip().lower() or None
    normalised_phone = (phone or "").strip() or None
    seed = normalised_email or normalised_phone
    if seed is None:
        raise MissingCustomerIdentityError(
            message="Cannot compute customer_source_id: neither email nor phone present.",
        )
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return digest[:_CUSTOMER_HASH_LENGTH]
