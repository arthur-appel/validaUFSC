"""Scraper do CAGR (árvore de Currículos dos Cursos, treeid=30).

Descoberta-chave: o relatório de currículo tem URL DIRETA e pública:
    https://cagr.sistemas.ufsc.br/relatorios/curriculoCurso?curso=<COD>&curriculo=<VIG>
Logo, só precisamos ENUMERAR os pares (curso, vigência). A árvore é um RichFaces 3.3.3
lazy-load: expandir um curso dispara um POST AJAX cuja resposta contém os links
`curriculoCurso?curso=X&curriculo=Y` de cada vigência. Coletamos esses links e baixamos
os PDFs por HTTP simples (sem sessão).

Política: pega a vigência mais recente (maior) de cada curso; rate-limit; pula PDFs já baixados.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from valida_ufsc.config import settings

_HOST = f"{urlsplit(settings.cagr_tree_url).scheme}://{urlsplit(settings.cagr_tree_url).netloc}"
_REPORT_URL = _HOST + "/relatorios/curriculoCurso?curso={curso}&curriculo={vig}"
_LINK_RE = re.compile(r"curriculoCurso\?curso=(\d+)&(?:amp;)?curriculo=(\d+)")


def _log(msg: str) -> None:
    sys.stdout.buffer.write((msg + "\n").encode("utf-8", "replace"))
    sys.stdout.flush()


def _expandir(page, texto: str, capturar: bool = False) -> str | None:
    """Expande o nó cujo TD tem exatamente `texto`.

    Retorna None se o nó não existe; senão o corpo do POST AJAX (vazio se não capturado)."""
    handle = page.evaluate_handle(
        """(t)=>{const td=[...document.querySelectorAll('td')].find(x=>x.textContent.trim()===t);
            if(!td)return null; let r=td; while(r&&r.tagName!=='TR')r=r.parentElement;
            return r?r.querySelector('img.rich-tree-node-handleicon-collapsed'):null;}""",
        texto,
    )
    el = handle.as_element()
    if el is None:
        return None
    body = ""
    try:
        with page.expect_response(
            lambda r: "arvore.xhtml" in r.url and r.request.method == "POST", timeout=15000
        ) as info:
            el.click()
        if capturar:
            body = info.value.text()
    except Exception:  # noqa: BLE001
        page.wait_for_timeout(2000)
    page.wait_for_timeout(900)  # settle do re-render RichFaces
    return body


def coletar_pares(campus: str, limit: int | None = None) -> dict[str, int]:
    """Retorna {curso_codigo: vigencia_mais_recente} para os cursos do campus."""
    from playwright.sync_api import sync_playwright

    pares: dict[str, int] = {}
    with sync_playwright() as p:
        # --no-sandbox/--disable-dev-shm-usage: necessários ao rodar como root no Docker
        browser = p.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        page = browser.new_context().new_page()
        page.goto(settings.cagr_tree_url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1500)

        if _expandir(page, f"Campus Universitário {campus}") is None:
            _log(f"⚠ não foi possível expandir o campus '{campus}'")
            browser.close()
            return pares

        # nomes dos cursos = texto da linha (só o TD de rótulo tem texto), exceto "Campus ..."
        nomes = page.evaluate(
            """()=>[...document.querySelectorAll("tr[id*='lazyTreeNode:mainRow']")]
                .map(r=>r.textContent.trim().replace(/\\s+/g,' '))
                .filter(t=>t && !t.startsWith('Campus'))"""
        )
        # dedup preservando ordem
        nomes = list(dict.fromkeys(nomes))
        if limit:
            nomes = nomes[:limit]
        _log(f"→ {len(nomes)} cursos no campus {campus}")

        for nome in nomes:
            # a resposta AJAX é cumulativa (todo o estado expandido); contamos só os NOVOS
            antes = set(pares)
            body = _expandir(page, nome, capturar=True) or ""
            for curso, vig in _LINK_RE.findall(body):
                v = int(vig)
                if curso not in pares or v > pares[curso]:
                    pares[curso] = v
            novos = sorted(set(pares) - antes)
            _log(f"  ✓ {nome}: {novos}" if novos else f"  · {nome}: (sem código novo)")
        browser.close()
    return pares


def baixar_curriculos(
    out_dir: Path, campus: str | None = None, limit: int | None = None
) -> list[Path]:
    """Enumera os cursos do campus e baixa o PDF do currículo vigente de cada um."""
    campus = campus or settings.cagr_campus
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pares = coletar_pares(campus, limit=limit)
    _log(f"→ {len(pares)} cursos com currículo a baixar")

    baixados: list[Path] = []
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        for curso, vig in sorted(pares.items()):
            destino = out_dir / f"curriculo_{curso}_{vig}.pdf"
            if destino.exists() and destino.stat().st_size > 1000:
                baixados.append(destino)
                continue
            url = _REPORT_URL.format(curso=curso, vig=vig)
            try:
                r = client.get(url)
                if r.status_code == 200 and r.content[:5] == b"%PDF-":
                    destino.write_bytes(r.content)
                    baixados.append(destino)
                    _log(f"  ⬇ curso {curso} (vig {vig}) -> {destino.name} ({len(r.content)} bytes)")
                else:
                    _log(f"  ✗ curso {curso}: resposta inesperada ({r.status_code})")
            except Exception as e:  # noqa: BLE001
                _log(f"  ✗ curso {curso}: erro ao baixar ({e})")
            page_delay = settings.scraper_delay_ms / 1000
            if page_delay:
                import time

                time.sleep(page_delay)
    _log(f"✔ {len(baixados)} PDFs em {out_dir}")
    return baixados


if __name__ == "__main__":
    import os

    lim = int(os.getenv("SCRAPER_LIMIT", "0")) or None
    baixar_curriculos(Path(settings.data_dir), limit=lim)
