FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libdbus-1-3 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 libpango-1.0-0 \
    libcairo2 libatspi2.0-0 libx11-6 libxext6 libxcb1 \
    fonts-liberation fonts-noto-color-emoji \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN groupadd -r appuser && useradd -r -g appuser appuser

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

ENV PLAYWRIGHT_BROWSERS_PATH=/app/.playwright-browsers
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=0
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Flags critiques VPS — à lire dans main.py via os.environ
ENV CHROMIUM_FLAGS="--no-sandbox --disable-dev-shm-usage"

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

RUN uv run playwright install --with-deps chromium \
    && chown -R appuser:appuser /app/.playwright-browsers

COPY . .
RUN chown -R appuser:appuser /app

USER appuser

CMD ["uv", "run", "python", "main.py"]