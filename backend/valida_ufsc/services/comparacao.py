"""Serviço de comparação: liga o banco ao motor de equivalência, cacheia e calcula KPIs.

Fluxo: carrega disciplinas de origem/destino do currículo -> constrói índice de
equivalências oficiais e a função de similaridade (embeddings) -> roda o motor
-> persiste o resultado (cache por par de currículos + parâmetros).
"""

from __future__ import annotations

import hashlib

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from valida_ufsc.api.schemas import (
    ComparacaoOut,
    CursoOut,
    DisciplinaOut,
    ItemOut,
    KpisOut,
    OrigemOut,
)
from valida_ufsc.config import settings
from valida_ufsc.db.models import (
    Comparacao,
    ComparacaoItem,
    ComparacaoItemOrigem,
    Curriculo,
    CurriculoDisciplina,
    Disciplina,
    DisciplinaEmbedding,
    EquivalenciaOficial,
)
from valida_ufsc.embeddings import cosseno
from valida_ufsc.matching import (
    BOA_CHANCE,
    NAO_APROVEITA,
    CriterioConfig,
    DiscRef,
    EquivalenciaIndex,
    comparar,
)
from valida_ufsc.matching.types import (
    METODO_CODIGO,
    METODO_NENHUM,
    METODO_OFICIAL,
    METODO_SOMATORIO,
)

OBRIGATORIAS = {"Ob", "Es"}

# Faixa de confiança (tier) exibida ao aluno, derivada do método + status.
_METODOS_DIRETO = {METODO_CODIGO, METODO_OFICIAL, METODO_SOMATORIO}
TIER_DIRETO = "direto"
TIER_BOA_CHANCE = "boa_chance"
TIER_SEM = "sem"


def tier_do_item(metodo: str, status: str) -> str:
    """Classifica um item nas faixas da UI: 'direto' (alta confiança, determinístico),
    'boa_chance' (semântico, leva ao colegiado) ou 'sem' (sem candidata).

    O status é verificado ANTES do método: uma soma N:1 semântica tem método 'somatorio'
    mas status 'boa_chance', e deve cair na faixa boa chance (não na determinística)."""
    if metodo == METODO_NENHUM or status == NAO_APROVEITA:
        return TIER_SEM
    if status == BOA_CHANCE:
        return TIER_BOA_CHANCE
    if metodo in _METODOS_DIRETO:
        return TIER_DIRETO
    return TIER_BOA_CHANCE


def config_padrao(
    limiar_conteudo: float | None = None, limiar_carga_horaria: float | None = None
) -> CriterioConfig:
    return CriterioConfig(
        limiar_conteudo=limiar_conteudo if limiar_conteudo is not None else settings.limiar_conteudo,
        limiar_boa_chance=settings.limiar_boa_chance,
        fator_ch=limiar_carga_horaria if limiar_carga_horaria is not None else settings.limiar_carga_horaria,
    )


# Versão da LÓGICA do motor. Bump a cada mudança de comportamento (faixas, somatório, etc.)
# para invalidar o cache de comparações automaticamente — senão F5 devolve resultado antigo.
_MOTOR_VERSAO = "5-sem-llm"


def _params_hash(config: CriterioConfig) -> str:
    chave = (
        f"motor={_MOTOR_VERSAO}|{config.limiar_conteudo}|{config.limiar_boa_chance}|{config.fator_ch}"
        f"|emb={settings.embedding_model}"
    )
    return hashlib.sha256(chave.encode()).hexdigest()[:32]


def _disciplinas_do_curriculo(
    db: Session, curriculo_id: int, apenas_obrigatorias: bool = False
) -> list[tuple[Disciplina, CurriculoDisciplina]]:
    q = (
        select(Disciplina, CurriculoDisciplina)
        .join(CurriculoDisciplina, CurriculoDisciplina.disciplina_id == Disciplina.id)
        .where(CurriculoDisciplina.curriculo_id == curriculo_id)
        # ordem estável e significativa -> resultado determinístico (PG: ASC = nulls last)
        .order_by(CurriculoDisciplina.fase, CurriculoDisciplina.ordem, Disciplina.codigo)
    )
    if apenas_obrigatorias:
        q = q.where(CurriculoDisciplina.tipo.in_(OBRIGATORIAS))
    return list(db.execute(q).all())


def _to_ref(d: Disciplina) -> DiscRef:
    return DiscRef(
        codigo=d.codigo, nome=d.nome, carga_horaria_ha=d.carga_horaria_ha, ementa=d.ementa
    )


def _construir_similaridade(db: Session, disc_ids: list[int]):
    rows = db.execute(
        select(Disciplina.codigo, DisciplinaEmbedding.embedding)
        .join(DisciplinaEmbedding, DisciplinaEmbedding.disciplina_id == Disciplina.id)
        .where(Disciplina.id.in_(disc_ids))
    ).all()
    vetores = {codigo: list(emb) for codigo, emb in rows}

    def similaridade(o: DiscRef, d: DiscRef) -> float:
        va, vb = vetores.get(o.codigo), vetores.get(d.codigo)
        if va is None or vb is None:
            return 0.0
        return cosseno(va, vb)

    return similaridade


def _construir_equivalencias(db: Session, disc_ids: list[int]) -> EquivalenciaIndex:
    rows = db.execute(
        select(Disciplina.codigo, EquivalenciaOficial.equivalente_codigo)
        .join(EquivalenciaOficial, EquivalenciaOficial.disciplina_id == Disciplina.id)
        .where(EquivalenciaOficial.disciplina_id.in_(disc_ids))
    ).all()
    return EquivalenciaIndex([(cod, eq) for cod, eq in rows])


def computar_comparacao(
    db: Session,
    origem_curriculo_id: int,
    destino_curriculo_id: int,
    config: CriterioConfig | None = None,
) -> Comparacao:
    """Roda o motor para o par de currículos e PERSISTE o resultado (cache)."""
    config = config or CriterioConfig()

    origem = _disciplinas_do_curriculo(db, origem_curriculo_id)
    destino = _disciplinas_do_curriculo(db, destino_curriculo_id, apenas_obrigatorias=True)

    origem_discs = [d for d, _ in origem]
    destino_discs = [d for d, _ in destino]
    todos_ids = [d.id for d in origem_discs] + [d.id for d in destino_discs]

    similaridade = _construir_similaridade(db, todos_ids)
    equivalencias = _construir_equivalencias(db, todos_ids)

    resultados = comparar(
        [_to_ref(d) for d in origem_discs],
        [_to_ref(d) for d in destino_discs],
        equivalencias,
        similaridade,
        config,
    )

    cod_para_id = {d.codigo: d.id for d in origem_discs + destino_discs}

    comp = Comparacao(
        curriculo_origem_id=origem_curriculo_id,
        curriculo_destino_id=destino_curriculo_id,
        params_hash=_params_hash(config),
    )
    db.add(comp)
    db.flush()

    for r in resultados:
        item = ComparacaoItem(
            comparacao_id=comp.id,
            disciplina_destino_id=cod_para_id[r.destino.codigo],
            metodo=r.metodo,
            similaridade=r.similaridade,
            status=r.status,
            ch_ok=r.ch_ok,
            ch_cobertura_pct=r.ch_cobertura_pct,
            justificativa=r.justificativa,
        )
        db.add(item)
        db.flush()
        for o in r.origens:
            db.add(
                ComparacaoItemOrigem(
                    item_id=item.id,
                    disciplina_origem_id=cod_para_id[o.disc.codigo],
                    similaridade=o.similaridade,
                )
            )
    db.commit()
    return comp


def obter_comparacao(
    db: Session,
    origem_curriculo_id: int,
    destino_curriculo_id: int,
    config: CriterioConfig | None = None,
) -> Comparacao:
    """Retorna a comparação do cache (se existir) ou calcula e persiste."""
    config = config or CriterioConfig()
    ph = _params_hash(config)

    def _buscar() -> Comparacao | None:
        return db.scalar(
            select(Comparacao)
            .where(
                Comparacao.curriculo_origem_id == origem_curriculo_id,
                Comparacao.curriculo_destino_id == destino_curriculo_id,
                Comparacao.params_hash == ph,
            )
            .options(selectinload(Comparacao.itens))
        )

    existente = _buscar()
    if existente:
        return existente
    try:
        return computar_comparacao(db, origem_curriculo_id, destino_curriculo_id, config)
    except IntegrityError:
        # corrida: outra requisição persistiu a mesma comparação -> recupera o cache
        db.rollback()
        ja = _buscar()
        if ja is None:
            raise
        return ja


# ─────────────────────────── Serialização / KPIs ───────────────────────────

def _curso_out(db: Session, curriculo_id: int) -> CursoOut:
    curric = db.get(Curriculo, curriculo_id)
    n = db.scalar(
        select(func.count(CurriculoDisciplina.id)).where(
            CurriculoDisciplina.curriculo_id == curriculo_id
        )
    )
    return CursoOut(
        curriculo_id=curric.id,
        curso_codigo=curric.curso.codigo,
        curso_nome=curric.curso.nome,
        codigo_vigencia=curric.codigo_vigencia,
        habilitacao=curric.habilitacao,
        total_disciplinas=n,
    )


def _disc_out(d: Disciplina) -> DisciplinaOut:
    return DisciplinaOut(codigo=d.codigo, nome=d.nome, carga_horaria_ha=d.carga_horaria_ha)


def _economia_semestres(db: Session, destino_curriculo_id: int, ha_aproveitada: int) -> int:
    """Estimativa: CH aproveitada / CH média por fase do currículo de destino."""
    # Numerador e denominador usam o MESMO conjunto (todas as obrigatórias do destino),
    # para que a CH aproveitada e a CH média por semestre sejam coerentes.
    rows = db.execute(
        select(CurriculoDisciplina.fase, Disciplina.carga_horaria_ha)
        .join(Disciplina, Disciplina.id == CurriculoDisciplina.disciplina_id)
        .where(
            CurriculoDisciplina.curriculo_id == destino_curriculo_id,
            CurriculoDisciplina.tipo.in_(OBRIGATORIAS),
        )
    ).all()
    if not rows:
        return 0
    total_ha = sum(ha or 0 for _, ha in rows)
    fases = {f for f, _ in rows if f is not None}
    if len(fases) >= 2:
        ha_por_semestre = total_ha / len(fases)
    else:
        # currículo sem fases detectadas (alguns PDFs de humanas): usa um semestre típico UFSC
        ha_por_semestre = 360.0
    if ha_por_semestre <= 0:
        return 0
    return int(ha_aproveitada // ha_por_semestre)


def _montar_kpis(db: Session, destino_curriculo_id: int, itens: list[ItemOut]) -> KpisOut:
    diretas = sum(1 for i in itens if i.tier == TIER_DIRETO)
    boas = sum(1 for i in itens if i.tier == TIER_BOA_CHANCE)
    com_candidata = diretas + boas
    total = len(itens)
    # Economia conservadora: só as DIRETAS (alta confiança) contam horas "certas";
    # as boas chances dependem do colegiado, então não entram na estimativa.
    ha_direto = sum((i.destino.carga_horaria_ha or 0) for i in itens if i.tier == TIER_DIRETO)
    return KpisOut(
        total=total,
        diretas=diretas,
        boas_chances=boas,
        com_candidata=com_candidata,
        cobertura_pct=round(100 * com_candidata / total, 1) if total else 0.0,
        economia_semestres=_economia_semestres(db, destino_curriculo_id, ha_direto),
    )


def montar_resposta(db: Session, comp: Comparacao) -> ComparacaoOut:
    """Serializa uma comparação persistida (cache) para a resposta da API."""
    itens_orm = db.scalars(
        select(ComparacaoItem)
        .where(ComparacaoItem.comparacao_id == comp.id)
        .options(
            selectinload(ComparacaoItem.disciplina_destino),
            selectinload(ComparacaoItem.origens).selectinload(
                ComparacaoItemOrigem.disciplina_origem
            ),
        )
    ).all()

    itens: list[ItemOut] = []
    for it in itens_orm:
        tier = tier_do_item(it.metodo, it.status)
        itens.append(
            ItemOut(
                destino=_disc_out(it.disciplina_destino),
                origens=[
                    OrigemOut(disciplina=_disc_out(o.disciplina_origem), similaridade=o.similaridade)
                    for o in it.origens
                ],
                metodo=it.metodo,
                status=it.status,
                similaridade=it.similaridade,
                ch_ok=it.ch_ok,
                ch_cobertura_pct=it.ch_cobertura_pct,
                justificativa=it.justificativa,
                tier=tier,
            )
        )
    return ComparacaoOut(
        comparacao_id=comp.id,
        origem=_curso_out(db, comp.curriculo_origem_id),
        destino=_curso_out(db, comp.curriculo_destino_id),
        kpis=_montar_kpis(db, comp.curriculo_destino_id, itens),
        itens=itens,
    )


def _item_de_resultado(r) -> ItemOut:
    tier = tier_do_item(r.metodo, r.status)
    return ItemOut(
        destino=DisciplinaOut(
            codigo=r.destino.codigo, nome=r.destino.nome,
            carga_horaria_ha=r.destino.carga_horaria_ha,
        ),
        origens=[
            OrigemOut(
                disciplina=DisciplinaOut(
                    codigo=o.disc.codigo, nome=o.disc.nome,
                    carga_horaria_ha=o.disc.carga_horaria_ha,
                ),
                similaridade=o.similaridade,
            )
            for o in r.origens
        ],
        metodo=r.metodo,
        status=r.status,
        similaridade=r.similaridade,
        ch_ok=r.ch_ok,
        ch_cobertura_pct=r.ch_cobertura_pct,
        justificativa=r.justificativa,
        tier=tier,
    )


def resposta_personalizada(
    db: Session,
    origem_curriculo_id: int,
    destino_curriculo_id: int,
    codigos_aprovados: list[str],
    config: CriterioConfig | None = None,
) -> ComparacaoOut:
    """Comparação restrita às disciplinas que o aluno JÁ cursou (histórico).

    Não é cacheada (depende do histórico do aluno); calculada sob demanda.
    """
    config = config or CriterioConfig()
    origem_discs = db.scalars(
        select(Disciplina)
        .where(Disciplina.codigo.in_(codigos_aprovados))
        .order_by(Disciplina.codigo)  # determinismo
    ).all()
    destino = _disciplinas_do_curriculo(db, destino_curriculo_id, apenas_obrigatorias=True)
    destino_discs = [d for d, _ in destino]
    todos_ids = [d.id for d in origem_discs] + [d.id for d in destino_discs]

    resultados = comparar(
        [_to_ref(d) for d in origem_discs],
        [_to_ref(d) for d in destino_discs],
        _construir_equivalencias(db, todos_ids),
        _construir_similaridade(db, todos_ids),
        config,
    )
    itens = [_item_de_resultado(r) for r in resultados]
    return ComparacaoOut(
        comparacao_id=0,
        origem=_curso_out(db, origem_curriculo_id),
        destino=_curso_out(db, destino_curriculo_id),
        kpis=_montar_kpis(db, destino_curriculo_id, itens),
        itens=itens,
    )
