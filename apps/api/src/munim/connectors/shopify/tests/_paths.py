"""Test helpers: paths used by all Shopify connector tests.

The demo fixture lives at apps/api/data/fixtures/shopify/orders.json — both
the running app (via the connect endpoint) and these tests read the same file.
"""

from pathlib import Path

# apps/api/src/munim/connectors/shopify/tests/_paths.py
# -> apps/api/
_API_ROOT = Path(__file__).parents[5]

SHOPIFY_DEMO_FIXTURE_PATH = _API_ROOT / "data" / "fixtures" / "shopify" / "orders.json"
