"""POST /connectors/{name}/connect-demo — one-click enable for demo connectors.

Demo connectors (Meta Ads, Shiprocket) bundle their fixtures inside the
package; the credential blob carries no secret and no fixture path. The
endpoint upserts a `connector_credentials` row with `status=DEMO` so the
existing sync path recognises the connector as connected and triggers
`sync_full` on demand.

Real OAuth connectors (Shopify) reject this endpoint with `connector.not_demo`
so the frontend doesn't accidentally short-circuit the real connect flow.
"""

import json

from sqlmodel import Session, select

from munim.connectors.registry import ConnectorRegistry, UnknownConnectorError
from munim.models import ConnectorCredentials
from munim.modules.connectors.schemas import ConnectorView
from munim.modules.connectors.service import build_connector_view
from munim.shared.constants import ConnectorName, CredentialStatus, ErrorCode
from munim.shared.errors import MunimError


class ConnectorNotDemoError(MunimError):
    code = ErrorCode.CONNECTOR_NOT_DEMO.value
    http_status = 400
    message = "Connector is not a demo connector; use the regular Connect flow."


def connect_demo_endpoint(
    session: Session,
    merchant_id: str,
    name: str,
    registry: ConnectorRegistry,
) -> ConnectorView:
    try:
        connector_name = ConnectorName(name)
    except ValueError as exc:
        raise UnknownConnectorError(
            message=f"Connector {name!r} is not registered.",
            details={"connector": name, "known": [n.value for n in registry.names()]},
        ) from exc

    connector = registry.get(connector_name)
    if not connector.is_demo:
        raise ConnectorNotDemoError(
            message=f"Connector {name!r} is not a demo connector.",
            details={"connector": name},
        )

    blob = {"status": CredentialStatus.DEMO.value}
    existing = session.exec(
        select(ConnectorCredentials)
        .where(ConnectorCredentials.merchant_id == merchant_id)
        .where(ConnectorCredentials.connector == connector_name.value)
    ).first()
    if existing is None:
        session.add(
            ConnectorCredentials(
                merchant_id=merchant_id,
                connector=connector_name.value,
                auth_blob_encrypted=json.dumps(blob),
                status=CredentialStatus.DEMO.value,
            )
        )
    else:
        existing.auth_blob_encrypted = json.dumps(blob)
        existing.status = CredentialStatus.DEMO.value
        session.add(existing)
    session.flush()
    return build_connector_view(session, merchant_id, connector_name, registry)
