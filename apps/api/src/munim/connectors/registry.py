"""Connector registry — the seam that makes the BaseConnector abstraction
swappable. A new connector becomes available to every endpoint by adding one
line to `default_registry()`. Routers and services never reference a concrete
connector class.

Per docs/conventions.md §10: unknown lookups raise — no silent fallback,
no None.
"""

from collections.abc import Mapping

from munim.connectors.base import BaseConnector
from munim.connectors.meta_ads.connector import MetaAdsConnector
from munim.connectors.shiprocket.connector import ShiprocketConnector
from munim.connectors.shopify.connector import ShopifyConnector
from munim.shared.constants import ConnectorName, ErrorCode
from munim.shared.errors import MunimError


class UnknownConnectorError(MunimError):
    code = ErrorCode.CONNECTOR_UNKNOWN.value
    http_status = 404
    message = "Unknown connector."


class ConnectorRegistry:
    def __init__(self, connectors: Mapping[ConnectorName, BaseConnector]) -> None:
        self._connectors = dict(connectors)

    def get(self, name: ConnectorName) -> BaseConnector:
        connector = self._connectors.get(name)
        if connector is None:
            raise UnknownConnectorError(
                message=f"Connector {name.value!r} is not registered.",
                details={"connector": name.value, "known": [n.value for n in self._connectors]},
            )
        return connector

    def names(self) -> list[ConnectorName]:
        return list(self._connectors.keys())


def default_registry() -> ConnectorRegistry:
    return ConnectorRegistry(
        {
            ConnectorName.SHOPIFY: ShopifyConnector(),
            ConnectorName.META_ADS: MetaAdsConnector(),
            ConnectorName.SHIPROCKET: ShiprocketConnector(),
        }
    )
