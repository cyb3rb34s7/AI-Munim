from decimal import Decimal

import pytest

from munim.connectors.meta_ads.mapper import (
    UnexpectedSpendValueError,
    build_source_id,
    map_meta_ads_insight,
)


def _base_row() -> dict[str, object]:
    return {
        "campaign_id": "23847264829340001",
        "campaign_name": "Diwali Push",
        "date_start": "2026-04-15",
        "date_stop": "2026-04-15",
        "spend": "1245.67",
        "impressions": "45678",
        "clicks": "892",
        "ctr": "1.95",
        "cpm": "27.27",
        "actions": [
            {"action_type": "purchase", "value": "12"},
            {"action_type": "add_to_cart", "value": "47"},
        ],
    }


def test_maps_meta_insight_to_decimal_spend_and_int_counts() -> None:
    result = map_meta_ads_insight(_base_row())

    assert isinstance(result.spend_inr, Decimal)
    assert result.spend_inr == Decimal("1245.67")
    assert result.impressions == 45678
    assert result.clicks == 892
    assert result.purchases_attributed == 12
    assert result.add_to_carts_attributed == 47


def test_extracts_action_values_by_action_type_not_position() -> None:
    row = _base_row()
    row["actions"] = [
        {"action_type": "add_to_cart", "value": "100"},
        {"action_type": "link_click", "value": "555"},
        {"action_type": "purchase", "value": "9"},
    ]
    result = map_meta_ads_insight(row)
    assert result.purchases_attributed == 9
    assert result.add_to_carts_attributed == 100


def test_missing_purchase_action_returns_zero_not_raise() -> None:
    row = _base_row()
    row["actions"] = [{"action_type": "add_to_cart", "value": "47"}]
    result = map_meta_ads_insight(row)
    assert result.purchases_attributed == 0
    assert result.add_to_carts_attributed == 47


def test_missing_actions_list_returns_zero_for_both() -> None:
    row = _base_row()
    row.pop("actions")
    result = map_meta_ads_insight(row)
    assert result.purchases_attributed == 0
    assert result.add_to_carts_attributed == 0


def test_malformed_spend_raises_typed_error_not_silent_zero() -> None:
    row = _base_row()
    row["spend"] = "not-a-number"
    with pytest.raises(UnexpectedSpendValueError) as exc_info:
        map_meta_ads_insight(row)
    assert exc_info.value.code == "validation.bad_format"


def test_source_id_is_campaign_id_plus_date() -> None:
    row = _base_row()
    assert build_source_id(row) == "23847264829340001_2026-04-15"


def test_date_field_is_date_string_not_timestamp() -> None:
    result = map_meta_ads_insight(_base_row())
    assert result.date == "2026-04-15"
