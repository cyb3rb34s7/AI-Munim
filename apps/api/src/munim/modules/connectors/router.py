"""HTTP routes for /connectors/*."""

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session

from munim.connectors.registry import ConnectorRegistry, UnknownConnectorError, default_registry
from munim.modules.connectors.schemas import (
    ConnectorListResponse,
    ConnectResponse,
    SyncResponse,
)
from munim.modules.connectors.service import (
    connect_demo,
    list_connectors,
    sync_connector,
)
from munim.shared.constants import ConnectorName
from munim.shared.db import DEFAULT_MERCHANT_ID, get_session
from munim.shared.responses import SuccessEnvelope

router = APIRouter(prefix="/connectors", tags=["connectors"])


def _registry_dep() -> ConnectorRegistry:
    return default_registry()


def _resolve_name(name: str, registry: ConnectorRegistry) -> ConnectorName:
    """Resolve a raw string to a ConnectorName, raising UnknownConnectorError if invalid."""
    try:
        connector_name = ConnectorName(name)
    except ValueError:
        raise UnknownConnectorError(
            message=f"Connector {name!r} is not registered.",
            details={"connector": name, "known": [n.value for n in registry.names()]},
        ) from None
    # Also check that it's in the registry (name could be valid enum but not registered).
    registry.get(connector_name)
    return connector_name


@router.get("", response_model=SuccessEnvelope[ConnectorListResponse])
def list_endpoint(
    request: Request,
    session: Session = Depends(get_session),
    registry: ConnectorRegistry = Depends(_registry_dep),
) -> SuccessEnvelope[ConnectorListResponse]:
    connectors = list_connectors(session, DEFAULT_MERCHANT_ID, registry)
    return SuccessEnvelope(
        data=ConnectorListResponse(connectors=connectors),
        trace_id=request.state.trace_id,
    )


@router.post(
    "/{name}/connect",
    response_model=SuccessEnvelope[ConnectResponse],
)
def connect_endpoint(
    name: str,
    request: Request,
    session: Session = Depends(get_session),
    registry: ConnectorRegistry = Depends(_registry_dep),
) -> SuccessEnvelope[ConnectResponse]:
    connector_name = _resolve_name(name, registry)
    view = connect_demo(session, DEFAULT_MERCHANT_ID, connector_name)
    session.commit()
    return SuccessEnvelope(
        data=ConnectResponse(connector=view),
        trace_id=request.state.trace_id,
    )


@router.post(
    "/{name}/sync",
    response_model=SuccessEnvelope[SyncResponse],
)
async def sync_endpoint(
    name: str,
    request: Request,
    session: Session = Depends(get_session),
    registry: ConnectorRegistry = Depends(_registry_dep),
) -> SuccessEnvelope[SyncResponse]:
    connector_name = _resolve_name(name, registry)
    result = await sync_connector(session, DEFAULT_MERCHANT_ID, connector_name, registry)
    session.commit()
    return SuccessEnvelope(data=result, trace_id=request.state.trace_id)
