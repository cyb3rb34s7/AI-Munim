"""Cross-module enums.

Per docs/conventions.md §7: NO magic strings in critical comparisons. Status
checks, error codes, payment methods, entity types all live in StrEnums and
get mirrored to the frontend as `as const` unions.
"""

from enum import StrEnum


class ErrorCode(StrEnum):
    SYSTEM_UNEXPECTED = "system.unexpected"
    SYSTEM_DATABASE_UNAVAILABLE = "system.database_unavailable"
    VALIDATION_MISSING_FIELD = "validation.missing_field"
    VALIDATION_BAD_FORMAT = "validation.bad_format"
    CONNECTOR_NOT_CONFIGURED = "connector.not_configured"
    CONNECTOR_SYNC_FAILED = "connector.sync_failed"
    CONNECTOR_UNKNOWN = "connector.unknown"
    CONNECTOR_NOT_CONNECTED = "connector.not_connected"
    RECORD_NOT_FOUND = "record.not_found"


class EntityType(StrEnum):
    ORDER = "order"
    SHIPMENT = "shipment"
    AD_SPEND = "ad_spend"
    CUSTOMER = "customer"
    PRODUCT = "product"
    PAYMENT = "payment"


class SourceSystem(StrEnum):
    SHOPIFY = "shopify"
    META_ADS = "meta_ads"
    SHIPROCKET = "shiprocket"


class ConnectorName(StrEnum):
    SHOPIFY = "shopify"
    META_ADS = "meta_ads"
    SHIPROCKET = "shiprocket"


class PaymentMethod(StrEnum):
    COD = "cod"
    PREPAID = "prepaid"
    PARTIAL = "partial"


class CredentialStatus(StrEnum):
    CONNECTED = "connected"
    DEMO = "demo"
    ERROR = "error"


class RunLogKind(StrEnum):
    SYNC = "sync"
    CHAT = "chat"
    AGENT = "agent"
