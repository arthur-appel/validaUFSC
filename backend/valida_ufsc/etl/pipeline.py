"""Pipeline de ETL: (scraping ->) parsing -> load -> embeddings.

Executável como job: `python -m valida_ufsc.etl.pipeline`.
Garante o schema (alembic), opcionalmente raspa o CAGR, e carrega todos os PDFs de
`settings.data_dir` no Postgres, gerando os embeddings das ementas.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from sqlalchemy import func, select, text

import valida_ufsc
from valida_ufsc.config import settings
from valida_ufsc.db.models import Curriculo, CurriculoDisciplina, Disciplina
from valida_ufsc.db.session import SessionLocal
from valida_ufsc.etl.loader import gerar_embeddings_pendentes, load_curriculo
from valida_ufsc.etl.parser import parse_curriculo_pdf

ROOT = Path(valida_ufsc.__file__).resolve().parent.parent  # diretório com alembic.ini
_ETL_LOCK_KEY = 727301  # chave do advisory lock que serializa execuções do ETL


def _log(msg: str) -> None:
    sys.stdout.buffer.write((msg + "\n").encode("utf-8", "replace"))
    sys.stdout.flush()


def _metricas_qualidade(db) -> None:
    """Loga métricas de qualidade dos dados (% de nulos em campos best-effort)."""
    n_curric = db.scalar(select(func.count(Curriculo.id))) or 0
    n_disc = db.scalar(select(func.count(Disciplina.id))) or 0
    n_cd = db.scalar(select(func.count(CurriculoDisciplina.id))) or 0
    if not (n_curric and n_disc and n_cd):
        return
    sem_carga = db.scalar(
        select(func.count(Curriculo.id)).where(Curriculo.carga_total_ha.is_(None))
    )
    sem_ementa = db.scalar(
        select(func.count(Disciplina.id)).where(Disciplina.ementa.is_(None))
    )
    sem_fase = db.scalar(
        select(func.count(CurriculoDisciplina.id)).where(CurriculoDisciplina.fase.is_(None))
    )
    _log("→ qualidade dos dados:")
    _log(f"    currículos sem carga_total: {sem_carga}/{n_curric} ({100*sem_carga//n_curric}%)")
    _log(f"    disciplinas sem ementa:     {sem_ementa}/{n_disc} ({100*sem_ementa//n_disc}%)")
    _log(f"    vínculos sem fase:          {sem_fase}/{n_cd} ({100*sem_fase//n_cd}%)")


def migrar() -> None:
    _log("→ aplicando migrations (alembic upgrade head)")
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, check=True)


def carregar_pdfs() -> None:
    data_dir = Path(settings.data_dir)
    pdfs = sorted({p for p in data_dir.glob("*") if p.suffix.lower() == ".pdf"})
    if not pdfs:
        _log(f"⚠ nenhum PDF em {data_dir.resolve()}")
        return
    with SessionLocal() as db:
        # serializa execuções concorrentes do ETL (evita corrida no banco); liberado ao fechar a sessão
        db.execute(text("SELECT pg_advisory_lock(:k)"), {"k": _ETL_LOCK_KEY})
        for pdf in pdfs:
            try:
                parse = parse_curriculo_pdf(pdf)
                curric = load_curriculo(db, parse)
                _log(
                    f"✓ {pdf.name}: {parse.curso_codigo} {parse.curso_nome} "
                    f"({len(parse.disciplinas)} disciplinas) -> currículo #{curric.id}"
                )
            except Exception as e:  # noqa: BLE001 — não aborta o lote por causa de 1 PDF
                db.rollback()  # reseta a transação para não envenenar os próximos PDFs
                _log(f"✗ {pdf.name}: falha ao processar ({e})")
        _metricas_qualidade(db)
        _log("→ gerando embeddings das ementas (Ollama)")
        try:
            n = gerar_embeddings_pendentes(db)
            _log(f"✓ embeddings gerados/atualizados: {n}")
        except Exception as e:  # noqa: BLE001
            _log(f"⚠ embeddings não gerados ({e}). Rode novamente com o Ollama disponível.")


def main() -> None:
    migrar()
    if settings.scrape:
        try:
            from valida_ufsc.etl.scraper import baixar_curriculos

            _log("→ raspando currículos do CAGR (Campus Florianópolis)")
            baixar_curriculos(Path(settings.data_dir))
        except Exception as e:  # noqa: BLE001
            _log(f"⚠ scraping pulado/falhou ({e}). Carregando PDFs já presentes.")
    carregar_pdfs()
    _log("✔ pipeline concluído")


if __name__ == "__main__":
    main()
