"""FastAPI app composition. Wires middleware, error handlers, and module routers."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from munim.modules.agent_runs.router import router as agent_runs_router
from munim.modules.auth.router import router as auth_router
from munim.modules.chat.router import router as chat_router
from munim.modules.connectors.router import router as connectors_router
from munim.modules.health.router import router as health_router
from munim.modules.records.router import router as records_router
from munim.shared.config import get_settings
from munim.shared.db import init_db
from munim.shared.errors import install_error_handlers
from munim.shared.logging import configure_logging, get_logger
from munim.shared.trace import TraceIdMiddleware

SESSION_COOKIE_NAME = "munim_session"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    load_dotenv(override=False)
    configure_logging()
    log = get_logger("munim.startup")
    settings = get_settings()
    log.info("app.startup.beginning", env=settings.app_env)
    init_db()
    log.info("app.startup.completed", env=settings.app_env)
    yield
    log.info("app.shutdown.completed")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AI-Munim API",
        description="AI employee for D2C brands.",
        version="0.1.0",
        lifespan=lifespan,
    )
    # SessionMiddleware reads + writes the signed cookie on every request.
    # `same_site="lax"` is the right default for a same-origin SPA; "strict"
    # would block the post-OAuth redirect from carrying the cookie back.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret.get_secret_value(),
        session_cookie=SESSION_COOKIE_NAME,
        max_age=settings.session_cookie_max_age_days * 86400,
        same_site="lax",
        https_only=settings.session_https_only,
    )
    app.add_middleware(TraceIdMiddleware)
    install_error_handlers(app)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(connectors_router)
    app.include_router(records_router)
    app.include_router(chat_router)
    app.include_router(agent_runs_router)
    if settings.frontend_dist_path:
        _mount_frontend(app, Path(settings.frontend_dist_path))
    return app


def _mount_frontend(app: FastAPI, dist_path: Path) -> None:
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=dist_path, html=True), name="frontend")


app = create_app()
