"""Smoke test da camada HTTP (FastAPI TestClient) contra o Postgres em execução."""

import sys

from fastapi.testclient import TestClient

from valida_ufsc.api.main import app


def out(s: str) -> None:
    sys.stdout.buffer.write((s + "\n").encode("utf-8", "replace"))


c = TestClient(app)

out(f"GET /health -> {c.get('/health').status_code}")

r = c.get("/cursos")
cursos = r.json()
out(f"GET /cursos -> {r.status_code} ({len(cursos)} cursos: {[x['curso_codigo'] for x in cursos]})")

origem = next(x["curriculo_id"] for x in cursos if x["curso_codigo"] == "349")
destino = next(x["curriculo_id"] for x in cursos if x["curso_codigo"] == "208")

r2 = c.post(
    "/comparacoes",
    json={"origem_curriculo_id": origem, "destino_curriculo_id": destino},
)
out(f"POST /comparacoes -> {r2.status_code}")
out(f"  kpis: {r2.json()['kpis']}")
out(f"  itens: {len(r2.json()['itens'])}")

# casos de erro (validação do router)
e1 = c.post("/comparacoes", json={"origem_curriculo_id": origem, "destino_curriculo_id": origem})
out(f"POST origem==destino -> {e1.status_code} (esperado 400): {e1.json().get('detail')}")

e2 = c.post("/comparacoes", json={"origem_curriculo_id": 99999, "destino_curriculo_id": destino})
out(f"POST currículo inexistente -> {e2.status_code} (esperado 404): {e2.json().get('detail')}")

e3 = c.post("/historico", files={"file": ("x.txt", b"nao sou pdf", "text/plain")})
out(f"POST histórico não-PDF -> {e3.status_code} (esperado 415/422): {e3.json().get('detail')}")
