FROM python:3.12-slim

RUN pip install --no-cache-dir uv==0.13.5

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Dépendances d'abord, pour profiter du cache Docker.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev

EXPOSE 8000
CMD ["/app/.venv/bin/uvicorn", "rag_ai_act_rgpd.api:app", "--host", "0.0.0.0", "--port", "8000"]
