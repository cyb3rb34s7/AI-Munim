"""Cross-module enums.

Per docs/conventions.md §7: NO magic strings in critical comparisons. Status
checks, error codes, payment methods, entity types all live in StrEnums and
get mirrored to the frontend as `as const` unions.

This file is sparse in Phase 1 and grows as features land. The shape is:
  - ErrorCode lives here from day one (used by the error envelope).
  - Domain enums (EntityType, PaymentMethod, ShipmentStatus, ...) join in Phase 2.
"""

from enum import StrEnum


class ErrorCode(StrEnum):
    SYSTEM_UNEXPECTED = "system.unexpected"
    SYSTEM_DATABASE_UNAVAILABLE = "system.database_unavailable"
    VALIDATION_MISSING_FIELD = "validation.missing_field"
    VALIDATION_BAD_FORMAT = "validation.bad_format"
