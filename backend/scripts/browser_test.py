"""Browser test do fluxo final: seleciona cursos -> Analisar (instantâneo) -> Refinar com IA.

Uso: python scripts/browser_test.py "ORIGEM" "DESTINO"
"""

import sys
import time

from playwright.sync_api import sync_playwright

ORIGEM = sys.argv[1] if len(sys.argv) > 1 else "ADMINISTRAÇÃO"
DESTINO = sys.argv[2] if len(sys.argv) > 2 else "CIÊNCIAS ECONÔMICAS"


def out(s: str) -> None:
    sys.stdout.buffer.write((s + "\n").encode("utf-8", "replace"))


with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=["--no-sandbox"])
    pg = b.new_page()
    pg.goto("http://localhost:5173", wait_until="networkidle", timeout=60000)
    pg.wait_for_timeout(2500)

    sels = pg.query_selector_all("select")

    def pick(sel, termo):
        v = sel.evaluate(
            "(s,t)=>{const o=[...s.options].find(o=>o.text.toUpperCase().includes(t.toUpperCase())); return o?o.value:''}",
            termo,
        )
        sel.select_option(value=v)
        return sel.evaluate("s=>s.options[s.selectedIndex].text")

    out(f"origem:  {pick(sels[0], ORIGEM)}")
    out(f"destino: {pick(sels[1], DESTINO)}")

    t = time.time()
    pg.get_by_role("button", name="Analisar Aproveitamento").click()
    pg.wait_for_selector("table tbody tr", timeout=60000)
    pg.wait_for_timeout(800)
    out(f"⚡ comparação carregou em {time.time()-t:.1f}s (instantânea)")

    kpis = pg.eval_on_selector_all(".text-3xl", "els => els.map(e => e.textContent.trim())")
    out(f"KPIs: {kpis}")
    botoes = pg.get_by_role("button", name="Refinar com IA")
    n_antes = botoes.count()
    out(f"itens com 'Refinar com IA': {n_antes}")
    pg.screenshot(path="scripts/app_1_instantaneo.png", full_page=True)

    if n_antes > 0:
        out("\n→ clicando em 'Refinar com IA' no 1º item…")
        t = time.time()
        botoes.first.click()
        try:
            pg.wait_for_selector("text=refinando…", state="visible", timeout=8000)
            pg.wait_for_selector("text=refinando…", state="hidden", timeout=120000)
            out(f"⏱ refino concluído em {time.time()-t:.0f}s")
        except Exception as e:  # noqa: BLE001
            out(f"  (espera do refino: {str(e)[:60]})")
        pg.wait_for_timeout(1000)
        out(f"itens restantes com 'Refinar com IA': {pg.get_by_role('button', name='Refinar com IA').count()}")
        pg.screenshot(path="scripts/app_2_refinado.png", full_page=True)

    b.close()
