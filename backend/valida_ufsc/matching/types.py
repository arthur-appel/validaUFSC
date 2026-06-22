"""Tipos de domínio do motor de equivalência (desacoplados do banco)."""

from __future__ import annotations

from dataclasses import dataclass, field

# Status possíveis de um item de auditoria.
APROVEITA = "aproveita"        # determinístico: mesmo código / equivalência oficial (alta confiança)
BOA_CHANCE = "boa_chance"      # semântico: ementa semelhante acima do corte — leve ao colegiado
RESSALVA = "ressalva"          # ressalva de carga horária (conteúdo ok, CH insuficiente)
NAO_APROVEITA = "nao_aproveita"  # sem candidata acima do corte

# Métodos pelos quais uma equivalência foi estabelecida (camadas do motor).
METODO_CODIGO = "codigo"
METODO_OFICIAL = "oficial"
METODO_SEMANTICO = "semantico"
METODO_SOMATORIO = "somatorio"
METODO_NENHUM = "nenhum"


@dataclass(frozen=True)
class DiscRef:
    """Referência mínima a uma disciplina (origem ou destino)."""

    codigo: str
    nome: str
    carga_horaria_ha: int | None = None
    ementa: str | None = None


@dataclass
class OrigemMatch:
    """Uma disciplina de origem que compõe a validação de uma de destino."""

    disc: DiscRef
    similaridade: float = 1.0


@dataclass
class ItemResult:
    """Resultado da auditoria para UMA disciplina de destino."""

    destino: DiscRef
    metodo: str
    status: str
    similaridade: float
    ch_ok: bool
    ch_cobertura_pct: float
    justificativa: str
    origens: list[OrigemMatch] = field(default_factory=list)


@dataclass
class CriterioConfig:
    """Limiares do critério oficial UFSC (configuráveis por colegiado).

    O corte `limiar_boa_chance` (0,70) foi CALIBRADO com os dados: as equivalências
    oficiais da UFSC (pares de fato equivalentes, com códigos distintos) ficam acima
    de ~0,70, enquanto 99% dos pares aleatórios ficam abaixo de 0,67 (piso do ruído).
    """

    limiar_conteudo: float = 0.75       # conteúdo "forte" (reforço por somatório N:1)
    limiar_boa_chance: float = 0.70     # >= => candidata a "boa chance" (corte calibrado)
    fator_ch: float = 0.75              # >= => carga horária suficiente (regra dos 75%)


class EquivalenciaIndex:
    """Índice simétrico das equivalências oficiais declaradas nos PDFs.

    Se a disciplina A declara B como equivalente, então cursar B valida A e vice-versa.
    """

    def __init__(self, pares: list[tuple[str, str]] | None = None) -> None:
        self._map: dict[str, set[str]] = {}
        for a, b in pares or []:
            self.add(a, b)

    def add(self, a: str, b: str) -> None:
        self._map.setdefault(a, set()).add(b)
        self._map.setdefault(b, set()).add(a)

    def equivalentes(self, codigo: str) -> set[str]:
        return self._map.get(codigo, set())
