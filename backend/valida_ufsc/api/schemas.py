"""Schemas Pydantic da API (respostas)."""

from __future__ import annotations

from pydantic import BaseModel


class ComparacaoIn(BaseModel):
    origem_curriculo_id: int
    destino_curriculo_id: int
    limiar_conteudo: float | None = None      # default: settings (0.75)
    limiar_carga_horaria: float | None = None  # default: settings (0.75)


class PersonalizadaIn(ComparacaoIn):
    historico_token: str


class CursoOut(BaseModel):
    curriculo_id: int
    curso_codigo: str
    curso_nome: str
    codigo_vigencia: str
    habilitacao: str | None = None
    total_disciplinas: int


class DisciplinaOut(BaseModel):
    codigo: str
    nome: str
    carga_horaria_ha: int | None = None


class OrigemOut(BaseModel):
    disciplina: DisciplinaOut
    similaridade: float


class ItemOut(BaseModel):
    destino: DisciplinaOut
    origens: list[OrigemOut]
    metodo: str
    status: str
    similaridade: float
    ch_ok: bool
    ch_cobertura_pct: float
    justificativa: str
    tier: str = "sem"        # faixa de confiança: "direto" | "boa_chance" | "sem"


class KpisOut(BaseModel):
    total: int            # disciplinas obrigatórias do destino analisadas
    diretas: int          # aproveitamento direto (código/equivalência oficial)
    boas_chances: int     # candidatas por similaridade de ementa (leva ao colegiado)
    com_candidata: int    # diretas + boas chances
    cobertura_pct: float  # % do destino com ao menos uma candidata
    economia_semestres: int  # estimativa conservadora (só as diretas)


class ComparacaoOut(BaseModel):
    comparacao_id: int
    origem: CursoOut
    destino: CursoOut
    kpis: KpisOut
    itens: list[ItemOut]


class HistoricoOut(BaseModel):
    token: str
    aluno: str | None
    curso_codigo: str
    curso_nome: str
    aprovadas: list[DisciplinaOut]
