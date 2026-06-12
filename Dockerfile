# Patchright needs a real Chromium with system libraries, so we base on the
# Playwright image (Patchright is API-compatible) and install via uv.
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

ENV PYTHONUNBUFFERED=1 \
    X_HEADLESS=true \
    X_BROWSER_CHANNEL=chromium \
    X_USER_DATA_DIR=/data

WORKDIR /app

# uv for fast, reproducible installs.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml README.md ./
COPY x_mcp_server ./x_mcp_server

RUN uv pip install --system --no-cache . \
    && patchright install chromium

VOLUME ["/data"]

ENTRYPOINT ["x-mcp-server"]
