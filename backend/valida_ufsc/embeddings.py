"""Cliente de embeddings via Ollama + similaridade de cosseno.

Usado pela ETL (popular `disciplina_embedding`) e pelo serviço de comparação
(similaridade entre ementas na camada semântica do motor).
"""

from __future__ import annotations

import math

import httpx

from valida_ufsc.config import settings


class OllamaEmbeddings:
    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.embedding_model

    def embed_many(self, textos: list[str], timeout: float = 120.0) -> list[list[float]]:
        """Gera embeddings em lote. Usa /api/embed (lote) com fallback p/ /api/embeddings."""
        if not textos:
            return []
        with httpx.Client(timeout=timeout) as client:
            try:
                r = client.post(
                    f"{self.base_url}/api/embed",
                    json={"model": self.model, "input": textos},
                )
                r.raise_for_status()
                data = r.json()
                if "embeddings" in data:
                    return data["embeddings"]
            except (httpx.HTTPError, KeyError):
                pass
            # fallback: endpoint single (um por vez)
            out: list[list[float]] = []
            for t in textos:
                r = client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": t},
                )
                r.raise_for_status()
                out.append(r.json()["embedding"])
            return out

    def embed(self, texto: str) -> list[float]:
        return self.embed_many([texto])[0]


def cosseno(a: list[float], b: list[float]) -> float:
    """Similaridade de cosseno em [0, 1] (clampada; ementas têm embeddings não-negativos
    o suficiente para ficar tipicamente em [0,1], mas garantimos o intervalo)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    sim = dot / (na * nb)
    return max(0.0, min(1.0, sim))
