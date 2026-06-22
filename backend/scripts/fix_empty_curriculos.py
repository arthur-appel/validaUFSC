"""Corrige currículos vigentes VAZIOS.

Alguns cursos têm como vigência mais nova um *placeholder* em branco no CAGR (ex.: 2027/1
ainda não preenchido). O scraper pega a vigência máxima, que nesses casos vem sem disciplinas.

Este script, para cada curso informado, baixa do CAGR (URL pública direta do relatório) as
vigências da mais nova para a mais antiga, parseia, e CARREGA a primeira que tiver conteúdo
(>= MIN_DISC disciplinas). O loader marca a carregada como vigente e rebaixa a placeholder.

Uso: python scripts/fix_empty_curriculos.py [curso ...]   (default: os 6 detectados)
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from urllib.parse import urlsplit

import httpx

from valida_ufsc.config import settings
from valida_ufsc.db.session import SessionLocal
from valida_ufsc.etl.loader import gerar_embeddings_pendentes, load_curriculo
from valida_ufsc.etl.parser import parse_curriculo_pdf

_HOST = f"{urlsplit(settings.cagr_tree_url).scheme}://{urlsplit(settings.cagr_tree_url).netloc}"
_REPORT = _HOST + "/relatorios/curriculoCurso?curso={curso}&curriculo={vig}"

# Vigências candidatas, da mais nova para a mais antiga (2026/2 .. 2008/1).
VIGS = [f"{y}{s}" for y in range(2026, 2007, -1) for s in (2, 1)]
MIN_DISC = 8
CURSOS_PADRAO = ["238", "201", "202", "216", "324", "455"]


def out(s: str) -> None:
    sys.stdout.buffer.write((s + "\n").encode("utf-8", "replace"))
    sys.stdout.flush()


def baixar_e_parsear(curso: str, vig: str):
    r = httpx.get(_REPORT.format(curso=curso, vig=vig), timeout=60, follow_redirects=True)
    if r.status_code != 200 or not r.content.startswith(b"%PDF"):
        return None
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(r.content)
        path = f.name
    try:
        return parse_curriculo_pdf(path)
    finally:
        os.unlink(path)


def main(cursos: list[str]) -> None:
    corrigidos: list[tuple[str, str, int]] = []
    with SessionLocal() as db:
        for curso in cursos:
            escolhido = None
            for vig in VIGS:
                try:
                    parse = baixar_e_parsear(curso, vig)
                except Exception as e:  # noqa: BLE001
                    out(f"  {curso}/{vig}: erro ({str(e)[:50]})")
                    parse = None
                time.sleep(0.2)
                if parse and len(parse.disciplinas) >= MIN_DISC:
                    escolhido = (vig, parse)
                    break
            if escolhido is None:
                out(f"✗ curso {curso}: nenhuma vigência com conteúdo encontrada")
                continue
            vig, parse = escolhido
            curric = load_curriculo(db, parse)
            n_ob = sum(1 for d in parse.disciplinas if d.tipo in ("Ob", "Es"))
            out(
                f"✓ curso {curso} -> vigência {vig}: {parse.curso_nome} "
                f"({len(parse.disciplinas)} disc, {n_ob} obrigatórias) [curric #{curric.id}]"
            )
            corrigidos.append((curso, vig, n_ob))

        out("→ gerando embeddings das ementas novas (Ollama)…")
        try:
            n = gerar_embeddings_pendentes(db)
            out(f"✓ embeddings gerados/atualizados: {n}")
        except Exception as e:  # noqa: BLE001
            out(f"⚠ embeddings não gerados ({e})")

    out(f"DONE: {len(corrigidos)}/{len(cursos)} cursos corrigidos -> {corrigidos}")


if __name__ == "__main__":
    main(sys.argv[1:] or CURSOS_PADRAO)
