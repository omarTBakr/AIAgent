# Runs the legal review worker as a standalone process.
#
# The build context is the project root, not this directory, because the worker
# imports activities/, workflows/, utils/ and friends:
#
#   docker build -f workers/legal_advice_worker/Docker/Dockerfile -t aiagent-legal-advice-worker .
#   docker run --rm --env-file .env aiagent-legal-advice-worker
#
# This image is only the worker. It polls LEGAL_TASK_QUEUE and executes
# workflows; it serves no HTTP and does not need a port.

FROM python:3.12-slim AS base

# uv resolves and installs from the committed lockfile
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app

# the user is created before anything is copied, so ownership can be set on the
# way in; a chown -R over the venv afterwards costs minutes per rebuild
RUN useradd --create-home --uid 1000 worker \
    && mkdir -p /app/assets \
    && chown -R worker:worker /app

WORKDIR /app
USER worker

# dependencies first: this layer is cached until pyproject or the lock changes
COPY --chown=worker:worker pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# then the source, which changes far more often
COPY --chown=worker:worker activities/ ./activities/
COPY --chown=worker:worker interfaces/ ./interfaces/
COPY --chown=worker:worker prompts/ ./prompts/
COPY --chown=worker:worker enums/ ./enums/
COPY --chown=worker:worker exceptions/ ./exceptions/
COPY --chown=worker:worker parsers/ ./parsers/
COPY --chown=worker:worker schemas/ ./schemas/
COPY --chown=worker:worker utils/ ./utils/
COPY --chown=worker:worker workers/ ./workers/
COPY --chown=worker:worker workflows/ ./workflows/

# localhost means the container itself, so the default is wrong in here; point
# it at wherever Temporal actually is
ENV TEMPORAL_HOST=host.docker.internal:7233

CMD ["python", "-m", "workers.legal_advice_worker"]
