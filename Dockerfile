# PaperTrail API + worker image (same image, different command).
# Build:  docker build -t papertrail .      Run both: docker compose up --build

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /usr/local/bin/uv

WORKDIR /app

# 1) Dependencies only (cached unless pyproject/uv.lock change)
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project --extra bedrock --extra aws

# 2) The application
COPY papertrail ./papertrail
RUN uv sync --locked --no-dev --extra bedrock --extra aws

# Run as an unprivileged user; data (SQLite + uploads) lives on a volume.
RUN useradd --system --uid 10001 --home /app app && mkdir -p /data && chown app /data
USER app

ENV PATH="/app/.venv/bin:$PATH" \
    PAPERTRAIL_SQLITE_PATH=/data/papertrail.db \
    PAPERTRAIL_UPLOAD_DIR=/data/uploads

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "papertrail.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
