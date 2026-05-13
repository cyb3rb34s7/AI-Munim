"""FastAPI app composition. Wires middleware, error handlers, and module routers."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from munim.modules.connectors.router import router as connectors_router
from munim.modules.health.router import router as health_router
from munim.modules.records.router import router as records_router
from munim.shared.config import get_settings
from munim.shared.db import init_db
from munim.shared.errors import install_error_handlers
from munim.shared.logging import configure_logging, get_logger
from munim.shared.trace import TraceIdMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    log = get_logger("munim.startup")
    settings = get_settings()
    log.info("app.startup.beginning", env=settings.app_env)
    init_db()
    log.info("app.startup.completed", env=settings.app_env)
    yield
    log.info("app.shutdown.completed")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI-Munim API",
        description="AI employee for D2C brands.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(TraceIdMiddleware)
    install_error_handlers(app)
    app.include_router(health_router)
    app.include_router(connectors_router)
    app.include_router(records_router)
    return app


app = create_app()
