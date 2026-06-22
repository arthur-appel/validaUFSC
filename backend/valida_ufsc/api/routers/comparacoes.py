"""Endpoints de auditoria de equivalência."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from valida_ufsc.api.schemas import (
    ComparacaoIn,
    ComparacaoOut,
    PersonalizadaIn,
)
from valida_ufsc.db.models import Curriculo, Historico
from valida_ufsc.db.session import get_session
from valida_ufsc.services.comparacao import (
    config_padrao,
    montar_resposta,
    obter_comparacao,
    resposta_personalizada,
)

router = APIRouter(prefix="/comparacoes", tags=["comparacoes"])


def _validar_curriculos(db: Session, origem_id: int, destino_id: int) -> None:
    for cid in (origem_id, destino_id):
        if db.get(Curriculo, cid) is None:
            raise HTTPException(status_code=404, detail=f"Currículo {cid} não encontrado.")
    if origem_id == destino_id:
        raise HTTPException(status_code=400, detail="Origem e destino devem ser diferentes.")


@router.post("", response_model=ComparacaoOut)
def criar_comparacao(payload: ComparacaoIn, db: Session = Depends(get_session)) -> ComparacaoOut:
    _validar_curriculos(db, payload.origem_curriculo_id, payload.destino_curriculo_id)
    config = config_padrao(payload.limiar_conteudo, payload.limiar_carga_horaria)
    comp = obter_comparacao(
        db,
        payload.origem_curriculo_id,
        payload.destino_curriculo_id,
        config,
    )
    return montar_resposta(db, comp)


@router.post("/personalizada", response_model=ComparacaoOut)
def comparacao_personalizada(
    payload: PersonalizadaIn, db: Session = Depends(get_session)
) -> ComparacaoOut:
    _validar_curriculos(db, payload.origem_curriculo_id, payload.destino_curriculo_id)
    hist = db.scalar(
        select(Historico)
        .where(Historico.token == payload.historico_token)
        .options(selectinload(Historico.disciplinas))
    )
    if hist is None:
        raise HTTPException(status_code=404, detail="Histórico não encontrado.")
    codigos = [d.codigo for d in hist.disciplinas if d.aprovado]
    config = config_padrao(payload.limiar_conteudo, payload.limiar_carga_horaria)
    return resposta_personalizada(
        db,
        payload.origem_curriculo_id,
        payload.destino_curriculo_id,
        codigos,
        config,
    )
