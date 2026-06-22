"""Loader ETL: grava um `CurriculoParse` no Postgres (upsert canônico) e gera embeddings.

Idempotente: re-rodar o pipeline atualiza dados sem duplicar. A `disciplina` é canônica
por código (UFSC-wide); `curriculo_disciplina` guarda o que varia por currículo (tipo/fase).
"""

from __future__ import annotations

import hashlib

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from valida_ufsc.config import settings
from valida_ufsc.db.models import (
    Curriculo,
    CurriculoDisciplina,
    Curso,
    Disciplina,
    DisciplinaEmbedding,
    EquivalenciaOficial,
    PreRequisito,
)
from valida_ufsc.embeddings import OllamaEmbeddings
from valida_ufsc.etl.parser import CurriculoParse


def _ementa_hash(ementa: str) -> str:
    return hashlib.sha256(ementa.encode("utf-8")).hexdigest()


def _get_or_create_curso(db: Session, codigo: str, nome: str) -> Curso:
    curso = db.scalar(select(Curso).where(Curso.codigo == codigo))
    if curso is None:
        curso = Curso(codigo=codigo, nome=nome, campus=settings.cagr_campus)
        db.add(curso)
        db.flush()
    elif nome and curso.nome != nome:
        curso.nome = nome
    return curso


def _get_or_create_curriculo(db: Session, curso: Curso, parse: CurriculoParse) -> Curriculo:
    curric = db.scalar(
        select(Curriculo).where(
            Curriculo.curso_id == curso.id,
            Curriculo.codigo_vigencia == parse.codigo_vigencia,
        )
    )
    if curric is None:
        curric = Curriculo(curso_id=curso.id, codigo_vigencia=parse.codigo_vigencia)
        db.add(curric)
    curric.habilitacao = parse.habilitacao
    curric.titulacao = parse.titulacao
    curric.carga_total_ha = parse.carga_total_ha
    curric.vigente = True
    db.flush()
    # apenas um currículo vigente por curso: rebaixa as demais vigências
    db.execute(
        update(Curriculo)
        .where(Curriculo.curso_id == curso.id, Curriculo.id != curric.id)
        .values(vigente=False)
    )
    return curric


def _upsert_disciplina(db: Session, dp) -> Disciplina:
    disc = db.scalar(select(Disciplina).where(Disciplina.codigo == dp.codigo))
    if disc is None:
        disc = Disciplina(
            codigo=dp.codigo,
            nome=dp.nome,
            ementa=dp.ementa or None,
            carga_horaria_ha=dp.carga_horaria_ha,
        )
        db.add(disc)
        db.flush()
        return disc
    # Política DETERMINÍSTICA (independe da ordem dos arquivos): vence o dado mais completo.
    if dp.nome and len(dp.nome) > len(disc.nome or ""):
        disc.nome = dp.nome
    if dp.ementa and len(dp.ementa) > len(disc.ementa or ""):
        disc.ementa = dp.ementa
    if dp.carga_horaria_ha:
        disc.carga_horaria_ha = max(disc.carga_horaria_ha or 0, dp.carga_horaria_ha)
    return disc


def load_curriculo(db: Session, parse: CurriculoParse) -> Curriculo:
    curso = _get_or_create_curso(db, parse.curso_codigo, parse.curso_nome)
    curric = _get_or_create_curriculo(db, curso, parse)

    presentes_ids: set[int] = set()
    for dp in parse.disciplinas:
        disc = _upsert_disciplina(db, dp)
        presentes_ids.add(disc.id)

        # junção currículo-disciplina (tipo/fase por currículo)
        cd = db.scalar(
            select(CurriculoDisciplina).where(
                CurriculoDisciplina.curriculo_id == curric.id,
                CurriculoDisciplina.disciplina_id == disc.id,
            )
        )
        if cd is None:
            cd = CurriculoDisciplina(curriculo_id=curric.id, disciplina_id=disc.id)
            db.add(cd)
        cd.tipo = dp.tipo
        cd.fase = dp.fase
        db.flush()

        # pré-requisitos (regrava)
        for pr in list(cd.pre_requisitos):
            db.delete(pr)
        if dp.pre_requisito:
            db.add(PreRequisito(curriculo_disciplina_id=cd.id, expressao_texto=dp.pre_requisito))

        # equivalências oficiais
        for eq_cod in dp.equivalentes:
            exists = db.scalar(
                select(EquivalenciaOficial).where(
                    EquivalenciaOficial.disciplina_id == disc.id,
                    EquivalenciaOficial.equivalente_codigo == eq_cod,
                )
            )
            if exists is None:
                db.add(
                    EquivalenciaOficial(disciplina_id=disc.id, equivalente_codigo=eq_cod)
                )

    # Carga declarativa: remove vínculos de disciplinas que saíram deste currículo
    # (evita linhas órfãs inflando KPIs/comparações ao re-rodar um PDF alterado).
    if presentes_ids:
        orfaos = db.scalars(
            select(CurriculoDisciplina).where(
                CurriculoDisciplina.curriculo_id == curric.id,
                CurriculoDisciplina.disciplina_id.not_in(presentes_ids),
            )
        ).all()
        for cd in orfaos:
            for pr in list(cd.pre_requisitos):
                db.delete(pr)
            db.delete(cd)

    db.commit()
    return curric


def gerar_embeddings_pendentes(db: Session, batch_size: int = 64) -> int:
    """Gera/atualiza embeddings das disciplinas cuja ementa mudou ou ainda não tem vetor."""
    client = OllamaEmbeddings()
    discs = db.scalars(select(Disciplina).where(Disciplina.ementa.is_not(None))).all()

    pendentes: list[Disciplina] = []
    for d in discs:
        h = _ementa_hash(d.ementa)
        emb = db.get(DisciplinaEmbedding, d.id)
        if emb is None or emb.ementa_hash != h or emb.modelo != client.model:
            pendentes.append(d)

    total = 0
    for i in range(0, len(pendentes), batch_size):
        lote = pendentes[i : i + batch_size]
        vetores = client.embed_many([d.ementa for d in lote])
        for d, vec in zip(lote, vetores):
            h = _ementa_hash(d.ementa)
            emb = db.get(DisciplinaEmbedding, d.id)
            if emb is None:
                emb = DisciplinaEmbedding(
                    disciplina_id=d.id, modelo=client.model, ementa_hash=h, embedding=vec
                )
                db.add(emb)
            else:
                emb.modelo = client.model
                emb.ementa_hash = h
                emb.embedding = vec
            total += 1
        db.commit()
    return total
