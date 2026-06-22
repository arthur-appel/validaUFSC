"""Upload e parsing do histórico escolar do aluno."""

from __future__ import annotations

import secrets
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from valida_ufsc.api.schemas import DisciplinaOut, HistoricoOut
from valida_ufsc.config import settings
from valida_ufsc.db.models import Historico, HistoricoDisciplina
from valida_ufsc.db.session import get_session
from valida_ufsc.etl.parser import parse_historico_pdf

router = APIRouter(prefix="/historico", tags=["historico"])


@router.post("", response_model=HistoricoOut)
async def upload_historico(
    file: UploadFile = File(...), db: Session = Depends(get_session)
) -> HistoricoOut:
    conteudo = await file.read()
    if not conteudo:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")
    if file.content_type not in (None, "application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=415, detail="Envie um arquivo PDF.")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(conteudo)
        tmp_path = Path(tmp.name)
    try:
        parse = parse_historico_pdf(tmp_path, nota_aprovacao=settings.nota_aprovacao)
    except Exception as exc:  # noqa: BLE001 — PDF inválido/ilegível vira erro de cliente
        raise HTTPException(
            status_code=422, detail="Não foi possível ler o PDF do histórico."
        ) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    token = secrets.token_hex(8)
    hist = Historico(
        token=token,
        aluno_nome=parse.aluno,
        curso_origem_nome=parse.curso_nome,
    )
    db.add(hist)
    db.flush()
    for d in parse.disciplinas:
        db.add(
            HistoricoDisciplina(
                historico_id=hist.id,
                codigo=d.codigo,
                nome=d.nome,
                nota=d.nota,
                carga_horaria_ha=d.carga_horaria_ha,
                aprovado=d.aprovado,
            )
        )
    db.commit()

    aprovadas = [
        DisciplinaOut(codigo=d.codigo, nome=d.nome, carga_horaria_ha=d.carga_horaria_ha)
        for d in parse.disciplinas
        if d.aprovado
    ]
    return HistoricoOut(
        token=token,
        aluno=parse.aluno,
        curso_codigo=parse.curso_codigo,
        curso_nome=parse.curso_nome,
        aprovadas=aprovadas,
    )
