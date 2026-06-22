"""Modelos ORM (schema do banco).

Insight central: `Disciplina.codigo` é único em toda a UFSC — a mesma disciplina
(ex. INE5111) aparece em vários currículos e históricos. Por isso `Disciplina` é a
entidade canônica, e os atributos que variam por currículo (tipo Ob/Op, fase) ficam
na junção `CurriculoDisciplina`.
"""

from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from valida_ufsc.config import settings
from valida_ufsc.db.base import Base


class Curso(Base):
    __tablename__ = "curso"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(16), unique=True, index=True)  # ex. "349"
    nome: Mapped[str] = mapped_column(String(255))
    campus: Mapped[str] = mapped_column(String(64), default="Florianópolis")

    curriculos: Mapped[list[Curriculo]] = relationship(back_populates="curso")


class Curriculo(Base):
    __tablename__ = "curriculo"
    __table_args__ = (UniqueConstraint("curso_id", "codigo_vigencia", name="uq_curriculo_vigencia"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    curso_id: Mapped[int] = mapped_column(ForeignKey("curso.id"), index=True)
    codigo_vigencia: Mapped[str] = mapped_column(String(16))  # ex. "20261"
    habilitacao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    titulacao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    carga_total_ha: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vigente: Mapped[bool] = mapped_column(Boolean, default=True)
    pdf_origem_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    curso: Mapped[Curso] = relationship(back_populates="curriculos")
    disciplinas: Mapped[list[CurriculoDisciplina]] = relationship(back_populates="curriculo")


class Disciplina(Base):
    """Entidade canônica UFSC-wide, chaveada pelo código (ex. CIN8001)."""

    __tablename__ = "disciplina"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    nome: Mapped[str] = mapped_column(String(255))
    ementa: Mapped[str | None] = mapped_column(Text, nullable=True)
    carga_horaria_ha: Mapped[int | None] = mapped_column(Integer, nullable=True)

    embedding: Mapped[DisciplinaEmbedding | None] = relationship(
        back_populates="disciplina", uselist=False
    )


class CurriculoDisciplina(Base):
    """Junção: tipo (Ob/Op/Es) e fase variam por currículo."""

    __tablename__ = "curriculo_disciplina"
    __table_args__ = (
        UniqueConstraint("curriculo_id", "disciplina_id", name="uq_curriculo_disciplina"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    curriculo_id: Mapped[int] = mapped_column(ForeignKey("curriculo.id"), index=True)
    disciplina_id: Mapped[int] = mapped_column(ForeignKey("disciplina.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(4), default="Ob")  # Ob | Op | Es | Ex
    fase: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = optativa/rol
    ordem: Mapped[int | None] = mapped_column(Integer, nullable=True)

    curriculo: Mapped[Curriculo] = relationship(back_populates="disciplinas")
    disciplina: Mapped[Disciplina] = relationship()
    pre_requisitos: Mapped[list[PreRequisito]] = relationship(
        back_populates="curriculo_disciplina"
    )


class PreRequisito(Base):
    __tablename__ = "pre_requisito"

    id: Mapped[int] = mapped_column(primary_key=True)
    curriculo_disciplina_id: Mapped[int] = mapped_column(
        ForeignKey("curriculo_disciplina.id"), index=True
    )
    expressao_texto: Mapped[str] = mapped_column(Text)  # ex. "(CIN8001 eh INE5111)"

    curriculo_disciplina: Mapped[CurriculoDisciplina] = relationship(
        back_populates="pre_requisitos"
    )


class EquivalenciaOficial(Base):
    """Equivalências declaradas na coluna 'Equivalentes' do PDF do currículo."""

    __tablename__ = "equivalencia_oficial"

    id: Mapped[int] = mapped_column(primary_key=True)
    disciplina_id: Mapped[int] = mapped_column(ForeignKey("disciplina.id"), index=True)
    equivalente_codigo: Mapped[str] = mapped_column(String(16), index=True)
    regra_texto: Mapped[str | None] = mapped_column(Text, nullable=True)


class DisciplinaEmbedding(Base):
    __tablename__ = "disciplina_embedding"

    disciplina_id: Mapped[int] = mapped_column(
        ForeignKey("disciplina.id"), primary_key=True
    )
    modelo: Mapped[str] = mapped_column(String(64))
    ementa_hash: Mapped[str] = mapped_column(String(64))  # detecta ementa alterada
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dim))

    disciplina: Mapped[Disciplina] = relationship(back_populates="embedding")


class Comparacao(Base):
    """Cache de uma auditoria por par (currículo origem, currículo destino, parâmetros)."""

    __tablename__ = "comparacao"
    __table_args__ = (
        UniqueConstraint(
            "curriculo_origem_id",
            "curriculo_destino_id",
            "params_hash",
            name="uq_comparacao_par",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    curriculo_origem_id: Mapped[int] = mapped_column(ForeignKey("curriculo.id"), index=True)
    curriculo_destino_id: Mapped[int] = mapped_column(ForeignKey("curriculo.id"), index=True)
    params_hash: Mapped[str] = mapped_column(String(64))  # limiares usados
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    itens: Mapped[list[ComparacaoItem]] = relationship(
        back_populates="comparacao", cascade="all, delete-orphan"
    )


class ComparacaoItem(Base):
    """Um resultado por disciplina de destino."""

    __tablename__ = "comparacao_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    comparacao_id: Mapped[int] = mapped_column(ForeignKey("comparacao.id"), index=True)
    disciplina_destino_id: Mapped[int] = mapped_column(ForeignKey("disciplina.id"))
    metodo: Mapped[str] = mapped_column(String(16))  # codigo|oficial|semantico|somatorio
    similaridade: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(16))  # aproveita|ressalva|nao_aproveita
    ch_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    ch_cobertura_pct: Mapped[float] = mapped_column(Float, default=0.0)
    justificativa: Mapped[str | None] = mapped_column(Text, nullable=True)

    comparacao: Mapped[Comparacao] = relationship(back_populates="itens")
    disciplina_destino: Mapped[Disciplina] = relationship()
    origens: Mapped[list[ComparacaoItemOrigem]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )


class ComparacaoItemOrigem(Base):
    """Origem(ns) que compõem o item — 1+ por item (suporta o somatório N:1)."""

    __tablename__ = "comparacao_item_origem"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("comparacao_item.id"), index=True)
    disciplina_origem_id: Mapped[int] = mapped_column(ForeignKey("disciplina.id"))
    similaridade: Mapped[float] = mapped_column(Float, default=0.0)

    item: Mapped[ComparacaoItem] = relationship(back_populates="origens")
    disciplina_origem: Mapped[Disciplina] = relationship()


class Historico(Base):
    """Histórico escolar enviado pelo aluno (por sessão/upload)."""

    __tablename__ = "historico"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    aluno_nome: Mapped[str | None] = mapped_column(String(255), nullable=True)
    curso_origem_nome: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    disciplinas: Mapped[list[HistoricoDisciplina]] = relationship(
        back_populates="historico", cascade="all, delete-orphan"
    )


class HistoricoDisciplina(Base):
    __tablename__ = "historico_disciplina"

    id: Mapped[int] = mapped_column(primary_key=True)
    historico_id: Mapped[int] = mapped_column(ForeignKey("historico.id"), index=True)
    codigo: Mapped[str] = mapped_column(String(16), index=True)
    nome: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nota: Mapped[float | None] = mapped_column(Float, nullable=True)
    carga_horaria_ha: Mapped[int | None] = mapped_column(Integer, nullable=True)
    aprovado: Mapped[bool] = mapped_column(Boolean, default=False)

    historico: Mapped[Historico] = relationship(back_populates="disciplinas")
