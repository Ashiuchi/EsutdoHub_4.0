import uuid
from datetime import datetime

from sqlalchemy import Column, String, Float, Integer, Text, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    # Fallback caso pgvector não esteja instalado no ambiente de build
    Vector = None

from app.db.database import Base


class CanonicalTopic(Base):
    """Tópico canonizado para padronização via embeddings."""

    __tablename__ = "canonical_topics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(255), nullable=False, index=True)
    area = Column(String(255), nullable=True)
    if Vector:
        embedding = Column(Vector(1024), nullable=False)
    else:
        embedding = Column(Text, nullable=False) # Fallback para evitar erro de inicialização


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
    
    anchor_text = Column(Text, nullable=True)
    syllabus_score = Column(Float, nullable=True)

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
    canonical_topic_id = Column(
        UUID(as_uuid=True),
        ForeignKey("canonical_topics.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    conteudo = Column(Text, nullable=False)

    if Vector:
        embedding = Column(Vector(1024), nullable=True)
    else:
        embedding = Column(Text, nullable=True)

    materia = relationship("Materia", back_populates="topicos")
    canonical_topic = relationship("CanonicalTopic")


class Documento(Base):
    """Representa um arquivo da biblioteca do usuário (Livros, Resumos, Apostilas)."""

    __tablename__ = "documentos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=True, unique=True)
    status = Column(String(50), default="processando")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    topicos_atomicos = relationship("TopicoAtomico", back_populates="documento", cascade="all, delete-orphan")


class TopicoAtomico(Base):
    """Conteúdo extraído e classificado por IA, pronto para ser cruzado com editais."""

    __tablename__ = "topicos_atomicos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    documento_id = Column(UUID(as_uuid=True), ForeignKey("documentos.id", ondelete="CASCADE"), nullable=False)
    
    # Taxonomia
    materia = Column(String(100), nullable=False, index=True) # Ex: Português
    topico = Column(String(100), nullable=False, index=True)  # Ex: Crase
    
    # Conteúdo
    original_text = Column(Text, nullable=False)
    ai_summary = Column(Text, nullable=True) # O "O que é este trecho?" gerado pela IA
    flashcards = Column(Text, nullable=True) # JSON contendo Q&A
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    documento = relationship("Documento", back_populates="topicos_atomicos")


class BibliotecaItem(Base):
    """Material de estudo pessoal enviado por um usuário.

    O file_path nunca é exposto na API — apenas metadados e o texto extraído
    ficam acessíveis, garantindo que o PDF original não vaze para outros usuários.
    """

    __tablename__ = "biblioteca_items"
    __table_args__ = (
        UniqueConstraint("user_id", "content_hash", name="uq_biblioteca_user_hash"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(String(255), nullable=False, index=True)   # Clerk user ID
    filename = Column(String(500), nullable=False)              # display only
    file_size = Column(Integer, nullable=False)                 # bytes
    content_hash = Column(String(64), nullable=False)           # SHA-256
    file_path = Column(String(1000), nullable=False)            # internal — never in API response
    status = Column(String(50), nullable=False, default="processando")  # processando | concluido | erro
    page_count = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
