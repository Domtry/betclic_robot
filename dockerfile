FROM python:3.12-slim

# Dépendances système requises par Playwright/Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libdbus-1-3 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 libpango-1.0-0 \
    libcairo2 libatspi2.0-0 libx11-6 libxext6 libxcb1 \
    fonts-liberation fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

# Installer uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Installer les dépendances Python (couche mise en cache si pyproject.toml inchangé)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Installer Chromium via Playwright
RUN uv run playwright install chromium

# Copier le code source
COPY . .

CMD ["uv", "run", "python", "main.py"]
