FROM node:22-bookworm-slim AS web
WORKDIR /app/apps/mobile
COPY apps/mobile/package*.json ./
RUN npm ci
COPY apps/mobile/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.7.2 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY services/ services/
COPY scripts/serve.py scripts/serve.py
COPY --from=web /app/apps/mobile/dist apps/mobile/dist
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
EXPOSE 8765
HEALTHCHECK --start-period=120s --interval=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/health/ready')"
CMD ["python", "scripts/serve.py", "--host", "0.0.0.0"]
