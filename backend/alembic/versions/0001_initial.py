"""schema inicial + extensão pgvector

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-14
"""
from __future__ import annotations

from alembic import op

from valida_ufsc.db.base import Base
import valida_ufsc.db.models  # noqa: F401  (popula Base.metadata)

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # Extensão pgvector precisa existir antes de criar a coluna Vector.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind=bind)
    # Índice HNSW (cosseno) para busca de ementas similares.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_disciplina_embedding_hnsw "
        "ON disciplina_embedding USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.execute("DROP INDEX IF EXISTS ix_disciplina_embedding_hnsw")
    Base.metadata.drop_all(bind=bind)
