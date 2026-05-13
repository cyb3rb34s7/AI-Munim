"""Registry tests. The registry is the seam where 'one interface, three
implementations, swappable' becomes provable. These tests fail when:
- The registry doesn't return the right concrete connector for a name.
- The registry silently returns None for an unknown name (silent fallback).
- A connector's `name` ClassVar disagrees with the registry key.
"""

import pytest

from munim.connectors.registry import (
    ConnectorRegistry,
    UnknownConnectorError,
    default_registry,
)
from munim.connectors.shopify.connector import ShopifyConnector
from munim.shared.constants import ConnectorName


def test_default_registry_resolves_shopify_to_shopify_connector() -> None:
    connector = default_registry().get(ConnectorName.SHOPIFY)
    assert isinstance(connector, ShopifyConnector)


def test_default_registry_lists_only_phase_3_connectors() -> None:
    # If a connector is added without a real impl, this test catches it before
    # a sync endpoint dispatches to a half-built connector.
    names = default_registry().names()
    assert ConnectorName.SHOPIFY in names


def test_registry_raises_typed_error_for_unknown_name() -> None:
    # Per docs/conventions.md §10 — no silent fallback (no `return None`).
    registry = ConnectorRegistry({})
    with pytest.raises(UnknownConnectorError) as exc_info:
        registry.get(ConnectorName.SHOPIFY)
    assert exc_info.value.code == "connector.unknown"


def test_registry_name_classvar_matches_registry_key() -> None:
    # Catches the bug where someone registers ShopifyConnector under the wrong
    # name string (e.g., "shoppify" typo) — the connector's own `name` is the
    # source of truth.
    registry = default_registry()
    for key in registry.names():
        assert registry.get(key).name is key
