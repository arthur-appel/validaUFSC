FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependências de sistema mínimas (psycopg/pdfplumber usam wheels; libgl não é necessário aqui)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY valida_ufsc ./valida_ufsc
COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts

RUN pip install --upgrade pip && pip install -e .

EXPOSE 8000

CMD ["uvicorn", "valida_ufsc.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
