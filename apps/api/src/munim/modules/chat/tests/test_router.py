"""Endpoint tests using PydanticAI's TestModel to mock the LLM.

We can't easily inject the TestModel through TestClient — the agent is
constructed inside the request handler. So these tests monkeypatch
`build_agent` to return a TestModel-backed agent.
"""

from datetime import UTC, datetime

import pytest
from conftest import AuthClient
from fastapi.testclient import TestClient
from pydantic_ai.models.test import TestModel

from munim.chat.types import GroundedAnswer
from munim.models import Record
from munim.shared.constants import EntityType, SourceSystem


def _seed_one_order(session, merchant_id: str) -> int:  # type: ignore[no-untyped-def]
    row = Record(
        merchant_id=merchant_id,
        source_system=SourceSystem.SHOPIFY.value,
        source_id="ord_test_chat",
        entity_type=EntityType.ORDER.value,
        fetched_at=datetime.now(UTC),
        payload_hash="h_chat",
        raw={"id": "ord_test_chat"},
        normalized={
            "placed_at": "2026-05-10T03:45:32Z",
            "total_inr": "1000.00",
            "payment_method": "cod",
            "financial_status": "pending",
            "pincode": "560001",
        },
    )
    session.add(row)
    session.commit()
    return row.id if row.id is not None else 0


def test_post_message_returns_text_with_citations(
    auth_client: AuthClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlmodel import Session

    from munim.shared.db import get_engine

    with Session(get_engine()) as s:
        order_id = _seed_one_order(s, auth_client.merchant_id)

    # call_tools=['_query_orders'] — the tool runs against the seeded DB,
    # returning the order as an available citation. The canned answer then
    # cites that real ID, so the enforcer accepts it.
    canned = GroundedAnswer(
        text=f"You have 1 order[cite:{order_id}] worth Rs.1000[cite:{order_id}].",
        used_citations=[order_id],
    )
    test_model = TestModel(call_tools=["_query_orders"], custom_output_args=canned)

    from munim.chat import agent as agent_module

    original_build = agent_module.build_agent

    def patched_build(model=None):  # type: ignore[no-untyped-def]
        return original_build(model=test_model)

    monkeypatch.setattr(agent_module, "build_agent", patched_build)

    response = auth_client.client.post("/chat/messages", json={"message": "How many orders?"})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "1 order" in body["data"]["text"]
    assert f"[cite:{order_id}]" in body["data"]["text"]
    assert len(body["data"]["citations"]) >= 1


def test_post_message_validates_input(auth_client: AuthClient) -> None:
    # Empty message must fail validation per §10.
    response = auth_client.client.post("/chat/messages", json={"message": ""})
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "validation.bad_format"


def test_unauthenticated_chat_returns_401(client: TestClient) -> None:
    response = client.post("/chat/messages", json={"message": "Hi"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth.unauthenticated"
