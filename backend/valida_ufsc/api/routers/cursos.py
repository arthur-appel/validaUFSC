"""Listagem de cursos/currículos vigentes (popula os selects de origem/destino)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from valida_ufsc.api.schemas import CursoOut
from valida_ufsc.db.models import Curriculo, CurriculoDisciplina
from valida_ufsc.db.session import get_session

router = APIRouter(prefix="/cursos", tags=["cursos"])


@router.get("", response_model=list[CursoOut])
def listar_cursos(db: Session = Depends(get_session)) -> list[CursoOut]:
    curriculos = db.scalars(
        select(Curriculo)
        .where(Curriculo.vigente.is_(True))
        .options(selectinload(Curriculo.curso))
    ).all()
    out: list[CursoOut] = []
    for c in curriculos:
        n = db.scalar(
            select(func.count(CurriculoDisciplina.id)).where(
                CurriculoDisciplina.curriculo_id == c.id
            )
        )
        if not n:
            # currículo vigente sem disciplinas (placeholder em branco no CAGR, ex.: vigência
            # 2027 ainda não preenchida) — não deve poluir os selects de origem/destino.
            continue
        out.append(
            CursoOut(
                curriculo_id=c.id,
                curso_codigo=c.curso.codigo,
                curso_nome=c.curso.nome,
                codigo_vigencia=c.codigo_vigencia,
                habilitacao=c.habilitacao,
                total_disciplinas=n or 0,
            )
        )
    out.sort(key=lambda x: x.curso_nome)
    return out
