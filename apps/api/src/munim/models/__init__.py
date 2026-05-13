"""SQLModel tables for the universal schema.

Importing this module registers every table on `SQLModel.metadata` so
`init_db()` creates them. Keep the imports here when adding a new table.
"""

from munim.models.connector_credentials import ConnectorCredentials
from munim.models.merchant import Merchant
from munim.models.record import Record
from munim.models.run_log import RunLog

__all__ = [
    "ConnectorCredentials",
    "Merchant",
    "Record",
    "RunLog",
]
