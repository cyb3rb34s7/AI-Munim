FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy

# uv from the official image (pinned via the docker-compose / Dockerfile, never `latest`).
COPY --from=ghcr.io/astral-sh/uv:0.5.0 /uv /uvx /usr/local/bin/

WORKDIR /app

# Install dependencies first for layer caching. Project source comes after so an
# edit to a .py file does not re-resolve the dep graph.
COPY pyproject.toml ./
RUN uv sync --no-install-project

# Now copy source and install the project package itself.
COPY src ./src
COPY conftest.py ./

RUN uv sync

EXPOSE 8000

# Default command is overridden by docker-compose for dev (adds --reload + volume).
CMD ["uv", "run", "uvicorn", "munim.main:app", "--host", "0.0.0.0", "--port", "8000"]
