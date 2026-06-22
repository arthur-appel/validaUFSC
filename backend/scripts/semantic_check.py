"""Validação da camada semântica (Ollama embeddings): gera embeddings e recompara 349->208."""

import sys

from sqlalchemy import delete, select

from valida_ufsc.db.models import (
    Comparacao,
    ComparacaoItem,
    ComparacaoItemOrigem,
    Curriculo,
    Curso,
)
from valida_ufsc.db.session import SessionLocal
from valida_ufsc.etl.loader import gerar_embeddings_pendentes
from valida_ufsc.services.comparacao import computar_comparacao, config_padrao, montar_resposta


def out(s: str) -> None:
    sys.stdout.buffer.write((s + "\n").encode("utf-8", "replace"))


with SessionLocal() as db:
    n = gerar_embeddings_pendentes(db)
    out(f"embeddings gerados/atualizados: {n}")

    # limpa cache (na ordem das dependências) para forçar recomputação com embeddings
    db.execute(delete(ComparacaoItemOrigem))
    db.execute(delete(ComparacaoItem))
    db.execute(delete(Comparacao))
    db.commit()

    origem = db.scalar(select(Curriculo).join(Curso).where(Curso.codigo == "349"))
    destino = db.scalar(select(Curriculo).join(Curso).where(Curso.codigo == "208"))
    comp = computar_comparacao(db, origem.id, destino.id, config_padrao())
    resp = montar_resposta(db, comp)

    out(f"\nKPIs: {resp.kpis.model_dump()}\n")
    out("Aproveitamentos (código + semântico via embeddings):")
    for it in resp.itens:
        if it.status != "nao_aproveita":
            origens = ", ".join(o.disciplina.codigo for o in it.origens)
            out(
                f"  [{it.status}/{it.metodo} {int(it.similaridade*100)}%] "
                f"{it.destino.codigo} {it.destino.nome[:34]} <- {origens}"
            )
