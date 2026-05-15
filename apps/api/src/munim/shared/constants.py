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
    CONNECTOR_NOT_DEMO = "connector.not_demo"
    CONNECTOR_INVALID_SHOP_DOMAIN = "connector.invalid_shop_domain"
    RECORD_NOT_FOUND = "record.not_found"
    AUTH_INVALID_STATE = "auth.invalid_state"
    AUTH_HMAC_MISMATCH = "auth.hmac_mismatch"
    AUTH_OAUTH_EXCHANGE_FAILED = "auth.oauth_exchange_failed"
    AUTH_CREDENTIAL_UNREADABLE = "auth.credential_unreadable"
    CHAT_LLM_UNAVAILABLE = "chat.llm_unavailable"
    CHAT_TOOL_FAILED = "chat.tool_failed"
    CHAT_UNVERIFIED_ANSWER = "chat.unverified_answer"
    AGENT_UNKNOWN = "agent.unknown"
    AGENT_RUN_FAILED = "agent.run_failed"
    AGENT_RUN_NOT_FOUND = "agent.run_not_found"


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


class MetricFormula(StrEnum):
    """Formulas accepted by `chat.tools.compute_metric`. No magic strings
    in the branching (§7) — the LLM passes one of these values; PydanticAI
    coerces it into the enum at the tool boundary.
    """

    SUM_TOTAL_INR = "sum_total_inr"
    COUNT_ORDERS = "count_orders"


class FulfillmentStatus(StrEnum):
    PENDING = "pending"
    FULFILLED = "fulfilled"
    PARTIAL = "partial"
    IN_TRANSIT = "in_transit"
    RTO = "rto"
    CANCELLED = "cancelled"


class AgentName(StrEnum):
    RTO_MITIGATOR = "rto_mitigator"


class AgentActionType(StrEnum):
    CONVERT_TO_PREPAID = "convert_to_prepaid"
    CONFIRMATION_CALL = "confirmation_call"
    NO_ACTION = "no_action"
