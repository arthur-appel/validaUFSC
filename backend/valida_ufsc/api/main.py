"""Aplicação FastAPI."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from valida_ufsc import __version__

app = FastAPI(title="Valida UFSC", version=__version__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


# Os routers (cursos, comparações, histórico) são incluídos na Fase 5.
try:
    from valida_ufsc.api.routers import comparacoes, cursos, historico

    app.include_router(cursos.router)
    app.include_router(comparacoes.router)
    app.include_router(historico.router)
except ImportError:
    # Routers ainda não implementados — mantém /health funcional.
    pass
