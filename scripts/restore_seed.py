"""Restaura o seed do banco (db/seed/seed.sql.gz) no Postgres do Docker Compose.

Uso (após `docker compose up -d`):
    python scripts/restore_seed.py

É a alternativa RÁPIDA ao ETL: em ~1 min você tem os 110 cursos + embeddings,
sem precisar raspar o CAGR nem gerar embeddings de novo. Cross-platform.
"""

from __future__ import annotations

import gzip
import subprocess
import sys
from pathlib import Path

SEED = Path(__file__).resolve().parent.parent / "db" / "seed" / "seed.sql.gz"
DB_SERVICE = "db"
PSQL = ["docker", "compose", "exec", "-T", DB_SERVICE, "psql", "-U", "valida", "-d", "valida_ufsc"]


def main() -> int:
    if not SEED.exists():
        print(f"✗ seed não encontrado em {SEED}")
        print("  Gere com:  docker compose exec -T db pg_dump -U valida -d valida_ufsc | gzip > db/seed/seed.sql.gz")
        return 1
    print(f"→ restaurando {SEED.name} no Postgres do Compose…")
    with gzip.open(SEED, "rb") as f:
        sql = f.read()
    proc = subprocess.run(PSQL, input=sql)
    if proc.returncode == 0:
        print("✔ seed restaurado. Acesse http://localhost:5173")
    else:
        print("✗ falha ao restaurar (o serviço 'db' está de pé? `docker compose up -d`)")
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
