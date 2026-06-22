"""Roda o parser num PDF e imprime um resumo (para validação manual)."""

import sys

from valida_ufsc.etl.parser import parse_curriculo_pdf

r = parse_curriculo_pdf(sys.argv[1])


def out(s: str) -> None:
    sys.stdout.buffer.write((s + "\n").encode("utf-8", "replace"))


out(f"Curso: {r.curso_codigo} - {r.curso_nome}")
out(f"Currículo: {r.codigo_vigencia} | Habilitação: {r.habilitacao}")
out(f"Titulação: {r.titulacao} | Carga total: {r.carga_total_ha}")
out(f"Total de disciplinas: {len(r.disciplinas)}")
out("")
for d in r.disciplinas:
    eq = f" equiv={d.equivalentes}" if d.equivalentes else ""
    pr = f" prereq='{d.pre_requisito}'" if d.pre_requisito else ""
    out(f"[{d.codigo}] {d.nome} | {d.tipo} fase={d.fase} ha={d.carga_horaria_ha} aulas={d.aulas}{eq}{pr}")
    out(f"    ementa: {d.ementa[:90]}")
