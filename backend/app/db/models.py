import uuid
from datetime import datetime

from sqlalchemy import Column, String, Float, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class Edital(Base):
    """Representa um edital de concurso público."""

    __tablename__ = "editais"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    title = Column(String(255), nullable=True)
    orgao = Column(String(255), nullable=False)
    banca = Column(String(255), nullable=False)
    published_at = Column(String(50), nullable=True)
    inscription_start = Column(String(50), nullable=True)
    inscription_end = Column(String(50), nullable=True)
    payment_deadline = Column(String(50), nullable=True)
    fee = Column(Float, nullable=True)
    exam_cities = Column(Text, nullable=True)
    data_prova = Column(String(50), nullable=True)
    link = Column(Text, nullable=True)
    content_hash = Column(String(64), nullable=True, unique=True, index=True)
    fingerprint = Column(String(64), nullable=True, index=True)
    status = Column(String(50), nullable=False, default="ingestado", server_default="ingestado")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    cargos = relationship("Cargo", back_populates="edital", cascade="all, delete-orphan")


class Cargo(Base):
    """Cargo dentro de um edital, com campos comerciais para monetização."""

    __tablename__ = "cargos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    edital_id = Column(UUID(as_uuid=True), ForeignKey("editais.id", ondelete="CASCADE"), nullable=False, index=True)
    titulo = Column(String(255), nullable=False)
    codigo_edital = Column(String(255), nullable=True)
    
    # DNA 26 Fields
    vagas_ac = Column(String(50), nullable=True)
    vagas_cr = Column(String(50), nullable=True)
    vagas_pcd = Column(String(50), nullable=True)
    vagas_negros = Column(String(50), nullable=True)
    vagas_indigenas = Column(String(50), nullable=True)
    vagas_trans = Column(String(50), nullable=True)
    vagas_total = Column(String(50), nullable=True)
    
    salario = Column(Float, nullable=True)
    escolaridade = Column(String(100), nullable=True)
    area = Column(String(255), nullable=True)
    atribuicoes = Column(Text, nullable=True)
    requisitos = Column(Text, nullable=True)
    lotation_cities = Column(Text, nullable=True)
    jornada = Column(String(100), nullable=True)
    
    status = Column(String(50), nullable=False, default="identificado")
    price = Column(Float, nullable=False, default=0.0)

    edital = relationship("Edital", back_populates="cargos")
    materias = relationship("Materia", back_populates="cargo", cascade="all, delete-orphan")


class Materia(Base):
    """Matéria exigida para um cargo específico."""

    __tablename__ = "materias"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    cargo_id = Column(UUID(as_uuid=True), ForeignKey("cargos.id", ondelete="CASCADE"), nullable=False, index=True)
    nome = Column(String(255), nullable=False)

    cargo = relationship("Cargo", back_populates="materias")
    topicos = relationship("Topico", back_populates="materia", cascade="all, delete-orphan")


class Topico(Base):
    """Tópico de conteúdo dentro de uma matéria."""

    __tablename__ = "topicos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    materia_id = Column(UUID(as_uuid=True), ForeignKey("materias.id", ondelete="CASCADE"), nullable=False, index=True)
    conteudo = Column(Text, nullable=False)

    materia = relationship("Materia", back_populates="topicos")
