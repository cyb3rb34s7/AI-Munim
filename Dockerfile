# Multi-stage build: Node stage builds the SPA, Python stage serves API + dist.
# The resulting image is a single Python process that exposes /api/* (FastAPI)
# and / (static SPA from the build stage's dist/ folder).

# ----- Stage 1: build the frontend with pnpm ---------------------------------
FROM node:22-alpine AS web-builder

RUN corepack enable && corepack prepare pnpm@9.15.0 --activate

WORKDIR /build

# Copy pnpm workspace + lockfile so dependency install layer caches well.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json ./apps/web/

RUN pnpm install --frozen-lockfile

# Now copy the web source and build.
COPY apps/web ./apps/web
ARG VITE_SHOPIFY_OAUTH_ENABLED=false
ENV VITE_SHOPIFY_OAUTH_ENABLED=${VITE_SHOPIFY_OAUTH_ENABLED}
RUN pnpm --filter @munim/web build

# ----- Stage 2: Python runtime ----------------------------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy

# uv from the official image (pinned, never `latest`).
COPY --from=ghcr.io/astral-sh/uv:0.5.0 /uv /uvx /usr/local/bin/

WORKDIR /app

# Install Python dependencies first for layer caching.
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --no-install-project --frozen

# Now copy source + conftest.
COPY apps/api/src ./src
COPY apps/api/conftest.py ./

RUN uv sync --frozen

# Copy the built SPA into the location FastAPI will mount as static files.
COPY --from=web-builder /build/apps/web/dist /app/static
ENV FRONTEND_DIST_PATH=/app/static

EXPOSE 8000

# `$PORT` is set by Render; falls back to 8000 for local docker run.
CMD ["sh", "-c", "uv run uvicorn munim.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
