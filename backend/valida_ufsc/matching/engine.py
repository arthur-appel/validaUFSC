"""Motor de equivalência em camadas (critério oficial UFSC), orientado a RECALL.

A ferramenta é um TRIADOR para o aluno: sugere o maior leque de disciplinas com chance
real de aproveitamento (o colegiado faz a decisão final). Por isso o resultado é dividido
em duas faixas claras de confiança, não num veredito definitivo:

  • APROVEITA   (faixa "direto")  — determinístico: mesmo código UFSC ou equivalência
                                    oficial declarada no PDF. Alta confiança.
  • BOA_CHANCE  (faixa "semântica") — ementa semelhante acima do corte calibrado
                                    (`limiar_boa_chance`, 0,70). Candidata a levar ao
                                    colegiado; NÃO é um veredito.

Para cada disciplina de DESTINO, em prioridade decrescente de confiança:

  1. Código exato         — mesmo código UFSC = disciplina idêntica  -> APROVEITA.
  2. Equivalência oficial — declarada na coluna "Equivalentes" do PDF -> APROVEITA.
  3. Semântico            — embeddings rankeiam; melhor candidato >= corte -> BOA_CHANCE.
  4. Somatório N:1        — combina 2+ origens para reforçar a carga horária do match direto.

Regra transversal de carga horária (regra dos 75%): no caminho determinístico, um match só
vira "aproveita" se cobrir >= `fator_ch` da CH do destino; senão tenta o somatório N:1 e, se
ainda assim não cobrir, cai para "ressalva" (de CH). Na faixa "boa chance", a CH é exibida
como informação (não filtra) — recall: quem decide CH é o colegiado.

A dependência externa de similaridade (embeddings) é INJETADA, tornando o motor 100%
testável offline.
"""

from __future__ import annotations

from collections.abc import Callable

from valida_ufsc.matching.types import (
    APROVEITA,
    BOA_CHANCE,
    METODO_CODIGO,
    METODO_NENHUM,
    METODO_OFICIAL,
    METODO_SEMANTICO,
    METODO_SOMATORIO,
    NAO_APROVEITA,
    RESSALVA,
    CriterioConfig,
    DiscRef,
    EquivalenciaIndex,
    ItemResult,
    OrigemMatch,
)

Similaridade = Callable[[DiscRef, DiscRef], float]


def _ch_cobertura(origem_total_ha: float, destino_ha: int | None) -> float | None:
    """Fração da CH do destino coberta pelas origens. None = CH do destino desconhecida."""
    if not destino_ha:
        return None
    if not origem_total_ha:
        return 0.0
    return origem_total_ha / destino_ha


def _make_item(
    destino: DiscRef,
    origens: list[OrigemMatch],
    metodo: str,
    status: str,
    similaridade: float,
    config: CriterioConfig,
    justificativa: str,
) -> ItemResult:
    total_ha = sum(o.disc.carga_horaria_ha or 0 for o in origens)
    cob = _ch_cobertura(total_ha, destino.carga_horaria_ha)
    ch_ok = cob is not None and cob >= config.fator_ch
    return ItemResult(
        destino=destino,
        metodo=metodo,
        status=status,
        similaridade=round(similaridade, 4),
        ch_ok=ch_ok,
        ch_cobertura_pct=round(cob if cob is not None else 0.0, 4),
        justificativa=justificativa,
        origens=origens,
    )


def comparar(
    origens: list[DiscRef],
    destinos: list[DiscRef],
    equivalencias: EquivalenciaIndex,
    similaridade: Similaridade,
    config: CriterioConfig | None = None,
) -> list[ItemResult]:
    config = config or CriterioConfig()

    # Dedup de origens por código (a mesma disciplina UFSC não deve concorrer consigo mesma).
    origens_unicas: list[DiscRef] = []
    _vistos: set[str] = set()
    for o in origens:
        if o.codigo not in _vistos:
            _vistos.add(o.codigo)
            origens_unicas.append(o)
    origem_por_codigo = {o.codigo: o for o in origens_unicas}

    consumidas: set[str] = set()
    # Resultados indexados por POSIÇÃO do destino (não por código — destinos podem repetir código).
    resultados: list[ItemResult | None] = [None] * len(destinos)

    def disponivel(o: DiscRef) -> bool:
        return o.codigo not in consumidas

    def consumir(ms: list[OrigemMatch]) -> None:
        for m in ms:
            consumidas.add(m.disc.codigo)

    def _ordenar(cands: list[OrigemMatch]) -> list[OrigemMatch]:
        # desempate estável e principiado: maior similaridade, maior CH, menor código
        cands.sort(key=lambda c: (-c.similaridade, -(c.disc.carga_horaria_ha or 0), c.disc.codigo))
        return cands

    def _pool_relacionado(destino: DiscRef, excluir: str | None = None) -> list[OrigemMatch]:
        cands = [
            OrigemMatch(o, similaridade(o, destino))
            for o in origens_unicas
            if disponivel(o) and o.codigo != excluir
        ]
        return _ordenar([c for c in cands if c.similaridade >= config.limiar_boa_chance])

    def _somatorio_topup(
        destino: DiscRef, base: OrigemMatch
    ) -> tuple[list[OrigemMatch], bool] | None:
        """Reforça a CH combinando a base com origens relacionadas até cobrir o alvo.

        Retorna (combo, todas_fortes) onde `todas_fortes` indica que TODAS as parcelas
        adicionadas têm conteúdo plenamente confirmado (sim >= limiar_conteudo)."""
        if not destino.carga_horaria_ha:
            return None
        alvo = config.fator_ch * destino.carga_horaria_ha
        escolhidas = [base]
        total = base.disc.carga_horaria_ha or 0
        for cand in _pool_relacionado(destino, excluir=base.disc.codigo):
            if total >= alvo:
                break
            escolhidas.append(cand)
            total += cand.disc.carga_horaria_ha or 0
        if total >= alvo and len(escolhidas) >= 2:
            adicionadas = escolhidas[1:]
            todas_fortes = all(o.similaridade >= config.limiar_conteudo for o in adicionadas)
            return escolhidas, todas_fortes
        return None

    def _resolver_conteudo(
        destino: DiscRef, base: OrigemMatch, metodo: str, sim: float, justificativa: str
    ) -> ItemResult:
        """Ponto ÚNICO de decisão para um match de conteúdo já confirmado.

        Aplica a regra dos 75% de carga horária e o somatório N:1, derivando o status."""
        cob = _ch_cobertura(base.disc.carga_horaria_ha or 0, destino.carga_horaria_ha)
        if cob is not None and cob >= config.fator_ch:
            item = _make_item(destino, [base], metodo, APROVEITA, sim, config, justificativa)
            consumir([base])
            return item

        # CH insuficiente ou desconhecida -> tenta reforço por somatório N:1
        combo = _somatorio_topup(destino, base)
        if combo is not None:
            escolhidas, todas_fortes = combo
            codigos = " + ".join(o.disc.codigo for o in escolhidas)
            status = APROVEITA if todas_fortes else RESSALVA
            extra = "" if todas_fortes else " Requer análise do colegiado."
            item = _make_item(
                destino, escolhidas, METODO_SOMATORIO, status, sim, config,
                f"Soma de disciplinas ({codigos}) cobre conteúdo e carga horária.{extra}",
            )
            consumir(escolhidas)
            return item

        if cob is None:
            just = f"{justificativa} Carga horária do destino não informada — requer análise do colegiado."
        else:
            just = f"{justificativa} Carga horária insuficiente ({cob:.0%} da exigida)."
        item = _make_item(destino, [base], metodo, RESSALVA, sim, config, just)
        consumir([base])
        return item

    # ── Pass 1: código exato ──────────────────────────────────────────────
    for i, d in enumerate(destinos):
        if resultados[i] is not None:
            continue
        o = origem_por_codigo.get(d.codigo)
        if o and disponivel(o):
            resultados[i] = _resolver_conteudo(
                d, OrigemMatch(o, 1.0), METODO_CODIGO, 1.0,
                "Mesmo código UFSC — disciplina idêntica.",
            )

    # ── Pass 2: equivalência oficial ──────────────────────────────────────
    for i, d in enumerate(destinos):
        if resultados[i] is not None:
            continue
        cand_cod = next(
            (c for c in equivalencias.equivalentes(d.codigo)
             if c in origem_por_codigo and disponivel(origem_por_codigo[c])),
            None,
        )
        if cand_cod:
            o = origem_por_codigo[cand_cod]
            resultados[i] = _resolver_conteudo(
                d, OrigemMatch(o, 1.0), METODO_OFICIAL, 1.0,
                f"Equivalência oficial declarada no currículo ({o.codigo} ≡ {d.codigo}).",
            )

    # ── Pass 3: semântico (embeddings rankeiam ementas) ────────────────────
    # Corte CALIBRADO `limiar_boa_chance` (0,70 — acima do piso do ruído de 0,67):
    #   melhor candidato >= corte  -> BOA_CHANCE (candidata; leva ao colegiado, NÃO é veredito)
    #   melhor candidato <  corte  -> descarta (-> sem candidata no pass 4)
    # RECALL: nesta faixa NÃO consumimos as origens — a mesma disciplina pode ser sugerida
    # para vários destinos (maximiza o leque; o colegiado valida cada origem em apenas um).
    # Ainda excluímos as já casadas por código/equivalência oficial (essas têm "lar" exato).
    for i, d in enumerate(destinos):
        if resultados[i] is not None:
            continue
        cands = [OrigemMatch(o, similaridade(o, d)) for o in origens_unicas if disponivel(o)]
        cands = [c for c in _ordenar(cands) if c.similaridade >= config.limiar_boa_chance]
        if not cands:
            continue
        melhor = cands[0]
        cob = _ch_cobertura(melhor.disc.carga_horaria_ha or 0, d.carga_horaria_ha)
        if cob is not None and cob < config.fator_ch:
            # A melhor origem sozinha não cobre 75% da CH -> tenta SOMAR com outras origens
            # semelhantes (N:1, regra oficial). Ex.: duas de 36h cobrem uma de 72h.
            combo = _somatorio_topup(d, melhor)
            if combo is not None:
                escolhidas, _ = combo
                codigos = " + ".join(o.disc.codigo for o in escolhidas)
                resultados[i] = _make_item(
                    d, escolhidas, METODO_SOMATORIO, BOA_CHANCE, melhor.similaridade, config,
                    f"Soma de {len(escolhidas)} disciplinas ({codigos}) cobre a carga horária "
                    f"exigida ({melhor.similaridade:.0%} de semelhança) — leve ao colegiado.",
                )
                continue
            # Sem como somar até 75%: a regra de CH é OBRIGATÓRIA e objetiva, então isoladamente
            # isto seria recusa CERTA do colegiado. Não é "boa chance" -> fica fora do formulário.
            resultados[i] = _make_item(
                d, [melhor], METODO_SEMANTICO, NAO_APROVEITA, melhor.similaridade, config,
                f"Conteúdo parecido ({melhor.similaridade:.0%}), mas carga horária insuficiente "
                f"({cob:.0%} da exigida) e sem disciplinas para somar — não atinge os 75% obrigatórios.",
            )
            continue
        # cob >= fator_ch (CH ok) ou cob is None (CH do destino desconhecida -> não dá p/ reprovar)
        ch_nota = (
            " Carga horária do destino não informada — confira com o colegiado." if cob is None else ""
        )
        resultados[i] = _make_item(
            d, [melhor], METODO_SEMANTICO, BOA_CHANCE, melhor.similaridade, config,
            f"Ementa semelhante ({melhor.similaridade:.0%}) — leve ao colegiado para análise.{ch_nota}",
        )

    # ── Pass 4: sem cobertura ─────────────────────────────────────────────
    for i, d in enumerate(destinos):
        if resultados[i] is None:
            resultados[i] = _make_item(
                d, [], METODO_NENHUM, NAO_APROVEITA, 0.0, config,
                "Nenhuma disciplina de origem compatível encontrada.",
            )

    return [r for r in resultados if r is not None]
