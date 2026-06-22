"""Verificação de integração (sem Ollama): carrega os 2 PDFs e roda a comparação
determinística (código/equivalência oficial) ponta-a-ponta pelo service."""

import sys

from sqlalchemy import select

from valida_ufsc.db.models import Curriculo, Curso
from valida_ufsc.db.session import SessionLocal
from valida_ufsc.etl.loader import load_curriculo
from valida_ufsc.etl.parser import parse_curriculo_pdf
from valida_ufsc.services.comparacao import config_padrao, montar_resposta, obter_comparacao


def out(s: str) -> None:
    sys.stdout.buffer.write((s + "\n").encode("utf-8", "replace"))


with SessionLocal() as db:
    for f in ["tests/fixtures/curso_origem.pdf", "tests/fixtures/curso_destino.pdf"]:
        p = parse_curriculo_pdf(f)
        c = load_curriculo(db, p)
        out(f"loaded: {p.curso_codigo} {p.curso_nome} -> currículo #{c.id} ({len(p.disciplinas)} disc)")

    origem = db.scalar(select(Curriculo).join(Curso).where(Curso.codigo == "349"))
    destino = db.scalar(select(Curriculo).join(Curso).where(Curso.codigo == "208"))
    out(f"\norigem=#{origem.id} (CD)  destino=#{destino.id} (Comp)\n")

    comp = obter_comparacao(db, origem.id, destino.id, config_padrao())
    resp = montar_resposta(db, comp)
    out(f"KPIs: {resp.kpis.model_dump()}\n")
    out("Itens com aproveitamento (sem embeddings, só código/oficial):")
    for it in resp.itens:
        if it.status != "nao_aproveita":
            origens = ", ".join(o.disciplina.codigo for o in it.origens)
            out(f"  [{it.status}/{it.metodo}] {it.destino.codigo} {it.destino.nome} <- {origens} (CH {it.ch_cobertura_pct:.0%})")
