FROM python:3.12-slim

# Bibliotecas de sistema exigidas pelo WeasyPrint (PDF).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libffi8 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
ENV PYTHONPATH=/app/src PATH="/app/.venv/bin:$PATH"

EXPOSE 8000
CMD ["uvicorn", "auditoria.main:app", "--host", "0.0.0.0", "--port", "8000"]
