from pydantic import BaseModel

from munim.shared.logging import get_logger

log = get_logger("munim.health")


class HealthData(BaseModel):
    status: str
    version: str


def check_health() -> HealthData:
    log.info("health.checked")
    return HealthData(status="ok", version="0.1.0")
