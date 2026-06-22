"""Testes do motor de equivalência (orientado a recall: faixas direto / boa chance).

Cobre as camadas, o corte calibrado (0,70), a regra dos 75% de CH, o somatório N:1 e —
explicitamente — cada achado da revisão adversarial ([REGRESSÃO #]).
"""

from valida_ufsc.matching import (
    APROVEITA,
    BOA_CHANCE,
    NAO_APROVEITA,
    RESSALVA,
    CriterioConfig,
    DiscRef,
    EquivalenciaIndex,
    comparar,
)

CFG = CriterioConfig()


def sim_de(tabela, default=0.0):
    def f(o: DiscRef, d: DiscRef) -> float:
        return tabela.get((o.codigo, d.codigo), default)

    return f


def sem_sim(o, d):
    return 0.0


def um(resultados):
    assert len(resultados) == 1
    return resultados[0]


# ── Camada 1: código exato (faixa "direto") ───────────────────────────────
def test_codigo_exato_aproveita():
    origens = [DiscRef("MTM3110", "Cálculo 1", 72)]
    destinos = [DiscRef("MTM3110", "Cálculo 1", 72)]
    r = um(comparar(origens, destinos, EquivalenciaIndex(), sem_sim))
    assert r.status == APROVEITA
    assert r.metodo == "codigo"
    assert r.ch_ok is True
    assert r.origens[0].disc.codigo == "MTM3110"


# ── Camada 2: equivalência oficial (faixa "direto") ───────────────────────
def test_equivalencia_oficial_aproveita():
    origens = [DiscRef("INE5382", "POO antiga", 108)]
    destinos = [DiscRef("INE5402", "POO I", 108)]
    eq = EquivalenciaIndex([("INE5402", "INE5382")])
    r = um(comparar(origens, destinos, eq, sem_sim))
    assert r.status == APROVEITA
    assert r.metodo == "oficial"


# ── Camada 3: semântico (faixa "boa chance") ──────────────────────────────
def test_semantico_acima_do_corte_vira_boa_chance():
    origens = [DiscRef("CIN8001", "Programação I", 108, "algoritmos")]
    destinos = [DiscRef("INE5402", "POO I", 108, "programação")]
    sim = sim_de({("CIN8001", "INE5402"): 0.82})
    r = um(comparar(origens, destinos, EquivalenciaIndex(), sim))
    assert r.status == BOA_CHANCE
    assert r.metodo == "semantico"
    assert r.similaridade == 0.82


def test_semantico_alto_continua_boa_chance_nao_aproveita_direto():
    # [HONESTIDADE] mesmo similaridade altíssima NÃO vira "aproveita": o embedding só rankeia;
    # equivalência de conteúdo é decisão do colegiado. Semântico nunca é "direto".
    origens = [DiscRef("AAA0001", "Cálculo I", 72, "limites e derivadas")]
    destinos = [DiscRef("BBB0002", "Cálculo Diferencial", 72, "derivadas")]
    sim = sim_de({("AAA0001", "BBB0002"): 0.96})
    r = um(comparar(origens, destinos, EquivalenciaIndex(), sim))
    assert r.status == BOA_CHANCE
    assert r.metodo == "semantico"


def test_corte_calibrado_separa_boa_chance_de_ruido():
    # [CALIBRAÇÃO] o corte é 0,70: 0,71 é candidata; 0,69 (zona de ruído) é descartado.
    origens = [DiscRef("AAA0001", "X", 72, "x")]
    acima = um(comparar(origens, [DiscRef("DST1", "alvo", 72, "y")],
                        EquivalenciaIndex(), sim_de({("AAA0001", "DST1"): 0.71})))
    abaixo = um(comparar(origens, [DiscRef("DST2", "alvo", 72, "y")],
                         EquivalenciaIndex(), sim_de({("AAA0001", "DST2"): 0.69})))
    assert acima.status == BOA_CHANCE
    assert abaixo.status == NAO_APROVEITA
    assert abaixo.metodo == "nenhum"


def test_semantico_baixo_sem_candidata():
    origens = [DiscRef("AAA0001", "Direito", 72)]
    destinos = [DiscRef("BBB0002", "Cálculo", 72)]
    sim = sim_de({("AAA0001", "BBB0002"): 0.30})
    r = um(comparar(origens, destinos, EquivalenciaIndex(), sim))
    assert r.status == NAO_APROVEITA


def test_ch_insuficiente_sem_soma_nao_e_candidata():
    # [REGRA OBRIGATÓRIA DE CH] conteúdo parecido mas CH < 75% e SEM como somar -> recusa certa
    # do colegiado; NÃO entra como "boa chance" (não faz sentido sugerir no formulário).
    origens = [DiscRef("AAA0001", "Intro", 36, "x")]
    destinos = [DiscRef("BBB0002", "Disciplina cheia", 120, "y")]
    sim = sim_de({("AAA0001", "BBB0002"): 0.78})
    r = um(comparar(origens, destinos, EquivalenciaIndex(), sim))
    assert r.status == NAO_APROVEITA
    assert r.ch_ok is False
    assert "carga horária insuficiente" in r.justificativa.lower()


def test_ch_desconhecida_continua_boa_chance():
    # CH do destino desconhecida -> não dá p/ reprovar pela regra de CH; segue como boa chance.
    origens = [DiscRef("AAA0001", "Intro", 36, "x")]
    destinos = [DiscRef("BBB0002", "Sem CH informada", None, "y")]
    sim = sim_de({("AAA0001", "BBB0002"): 0.78})
    r = um(comparar(origens, destinos, EquivalenciaIndex(), sim))
    assert r.status == BOA_CHANCE
    assert "não informada" in r.justificativa.lower()


# ── Regra dos 75% de carga horária (caminho determinístico) ───────────────
def test_ch_insuficiente_rebaixa_para_ressalva():
    origens = [DiscRef("MTM3110", "Cálculo 1", 36)]  # metade da CH do destino
    destinos = [DiscRef("MTM3110", "Cálculo 1", 72)]
    r = um(comparar(origens, destinos, EquivalenciaIndex(), sem_sim))
    assert r.status == RESSALVA
    assert r.ch_ok is False
    assert r.metodo == "codigo"


def test_destino_sem_ch_nao_vira_aproveita():
    # [REGRESSÃO 1] CH do destino desconhecida não deve aprovar o gate de CH
    origens = [DiscRef("MTM3110", "Cálculo 1", 72)]
    destinos = [DiscRef("MTM3110", "Cálculo 1", None)]
    r = um(comparar(origens, destinos, EquivalenciaIndex(), sem_sim))
    assert r.status == RESSALVA
    assert r.ch_ok is False
    assert "não informada" in r.justificativa


# ── Somatório N:1 (reforço de CH do match determinístico) ─────────────────
def test_somatorio_cobre_ch_com_conteudo_forte_vira_aproveita():
    # [REGRESSÃO 3] N:1 com conteúdo plenamente confirmado E CH coberta => aproveita
    origens = [
        DiscRef("MTM3110", "Cálculo 1", 36, "limites"),     # base (código), CH curta
        DiscRef("MTM9999", "Cálculo extra", 72, "integrais"),  # reforço forte
    ]
    destinos = [DiscRef("MTM3110", "Cálculo 1", 72, "cálculo")]
    sim = sim_de({("MTM9999", "MTM3110"): 0.85})
    r = um(comparar(origens, destinos, EquivalenciaIndex(), sim))
    assert r.status == APROVEITA
    assert r.metodo == "somatorio"
    assert len(r.origens) == 2
    assert r.ch_ok is True


def test_somatorio_semantico_combina_para_boa_chance():
    # [N:1 SEMÂNTICO] duas origens semelhantes de 36h cobrem um destino de 72h -> boa chance somada
    origens = [
        DiscRef("AAA0001", "Algoritmos I", 36, "x"),
        DiscRef("AAA0002", "Algoritmos II", 36, "y"),
    ]
    destinos = [DiscRef("BBB0003", "Programação", 72, "z")]
    sim = sim_de({("AAA0001", "BBB0003"): 0.82, ("AAA0002", "BBB0003"): 0.78})
    r = um(comparar(origens, destinos, EquivalenciaIndex(), sim))
    assert r.status == BOA_CHANCE
    assert r.metodo == "somatorio"
    assert len(r.origens) == 2
    assert r.ch_ok is True


def test_somatorio_com_parcela_fraca_vira_ressalva():
    origens = [
        DiscRef("MTM3110", "Cálculo 1", 36, "limites"),
        DiscRef("MTM9999", "Cálculo extra", 72, "integrais"),
    ]
    destinos = [DiscRef("MTM3110", "Cálculo 1", 72, "cálculo")]
    sim = sim_de({("MTM9999", "MTM3110"): 0.72})  # acima do corte, mas não "forte" (< 0,75)
    r = um(comparar(origens, destinos, EquivalenciaIndex(), sim))
    assert r.status == RESSALVA
    assert r.metodo == "somatorio"
    assert len(r.origens) == 2


# ── Edge cases dos achados ────────────────────────────────────────────────
def test_destinos_codigo_duplicado_avaliados_separadamente():
    # [REGRESSÃO 5] dois destinos com mesmo código não podem colidir
    origens = [DiscRef("X0001", "Cálculo A", 60, "calc")]
    destinos = [
        DiscRef("X0001", "Cálculo A", 60, "calc"),
        DiscRef("X0001", "Química B", 60, "quim"),
    ]
    r = comparar(origens, destinos, EquivalenciaIndex(), sem_sim)
    assert len(r) == 2
    assert r[0] is not r[1]
    assert r[0].destino.nome == "Cálculo A"
    assert r[1].destino.nome == "Química B"
    assert r[0].status == APROVEITA  # casou por código e consumiu a origem
    assert r[1].status == NAO_APROVEITA  # origem já consumida


def test_desempate_deterministico_independe_da_ordem():
    # [REGRESSÃO 6] empate de similaridade resolve por (sim, CH, código) — estável
    destino = [DiscRef("DST0001", "Alvo", 72, "t")]
    a = DiscRef("AAA0001", "a", 72, "x")
    b = DiscRef("BBB0001", "b", 72, "y")
    sim = sim_de({("AAA0001", "DST0001"): 0.9, ("BBB0001", "DST0001"): 0.9})
    r1 = um(comparar([a, b], destino, EquivalenciaIndex(), sim))
    r2 = um(comparar([b, a], destino, EquivalenciaIndex(), sim))
    assert r1.origens[0].disc.codigo == r2.origens[0].disc.codigo == "AAA0001"


def test_origem_reutilizada_na_faixa_boa_chance():
    # [REUSO/RECALL] na faixa "boa chance" a MESMA origem pode ser sugerida para vários
    # destinos (maximiza o leque; o colegiado valida cada origem em apenas um).
    origens = [DiscRef("AAA0001", "Estatística", 72, "x")]
    destinos = [
        DiscRef("DST0001", "Probabilidade", 72, "y"),
        DiscRef("DST0002", "Inferência", 72, "z"),
    ]
    sim = sim_de({("AAA0001", "DST0001"): 0.9, ("AAA0001", "DST0002"): 0.9})
    r = comparar(origens, destinos, EquivalenciaIndex(), sim)
    assert r[0].status == BOA_CHANCE
    assert r[1].status == BOA_CHANCE  # reusada (faixa semântica não consome)
    assert r[1].origens[0].disc.codigo == "AAA0001"


def test_codigo_consome_e_nao_e_reusado():
    # a faixa DETERMINÍSTICA (código/oficial) continua consumindo: 1 origem -> 1 destino.
    origens = [DiscRef("MTM3110", "Cálculo 1", 72)]
    destinos = [DiscRef("MTM3110", "Cálculo 1", 72), DiscRef("MTM3110", "Cálculo 1", 72)]
    r = comparar(origens, destinos, EquivalenciaIndex(), sem_sim)
    assert r[0].status == APROVEITA
    assert r[1].status == NAO_APROVEITA  # código já consumido pelo primeiro


def test_listas_vazias():
    assert comparar([], [], EquivalenciaIndex(), sem_sim) == []
    r = comparar([], [DiscRef("X0001", "x", 72)], EquivalenciaIndex(), sem_sim)
    assert um(r).status == NAO_APROVEITA
