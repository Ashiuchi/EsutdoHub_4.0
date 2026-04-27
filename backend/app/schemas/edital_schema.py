import uuid
from pydantic import BaseModel, Field
from typing import List, Optional


class StatusEdital:
    INGESTADO = "ingestado"
    PROCESSANDO = "processando"
    PROCESSADO = "processado"
    ERRO = "erro"


class Materia(BaseModel):
    nome: str
    topicos: List[str]
    peso: Optional[float] = 1.0
    quantidade_questoes: Optional[int] = 0

class Cargo(BaseModel):
    titulo: str
    codigo_edital: Optional[str] = None
    vagas_ac: Optional[str] = None
    vagas_cr: Optional[str] = None
    vagas_pcd: Optional[str] = None
    vagas_negros: Optional[str] = None
    vagas_indigenas: Optional[str] = None
    vagas_trans: Optional[str] = None
    vagas_total: Optional[str] = None
    salario: Optional[float] = 0.0
    escolaridade: Optional[str] = "Pendente"
    area: Optional[str] = "Pendente"
    atribuicoes: Optional[str] = "Pendente"
    requisitos: Optional[str] = "Pendente"
    lotation_cities: Optional[str] = "Pendente"
    jornada: Optional[str] = "Pendente"
    status: str = Field(default='identificado', description='Status comercial do cargo')
    price: float = Field(default=0.0, description='Preço de acesso ao conteúdo do cargo')
    materias: List[Materia] = Field(default=[], description='Lista de matérias exigidas para este cargo específico')

class EditalGeral(BaseModel):
    title: Optional[str] = "Pendente"
    orgao: str
    banca: str
    published_at: Optional[str] = "Pendente"
    inscription_start: Optional[str] = "Pendente"
    inscription_end: Optional[str] = "Pendente"
    payment_deadline: Optional[str] = "Pendente"
    fee: Optional[float] = 0.0
    exam_cities: Optional[str] = "Pendente"
    data_prova: Optional[str] = "Pendente"
    link_edital: Optional[str] = None
    content_hash: Optional[str] = None
    fingerprint: Optional[str] = None
    cargos: List[Cargo] = []


class EditalResponse(EditalGeral):
    """EditalGeral enriquecido com campos do banco após persistência."""
    id: Optional[uuid.UUID] = None
    status: str = StatusEdital.INGESTADO
    content_hash: Optional[str] = None
    fingerprint: Optional[str] = None


class CargoIdentificado(BaseModel):
    titulo: str
    codigo_edital: Optional[str] = None

class IngestionResponse(BaseModel):
    """Resposta simplificada após a ingestão e persistência do edital."""
    id: uuid.UUID
    content_hash: str
    status: str
    total_tables: Optional[int] = 0
    total_links: Optional[int] = 0
    total_chars: Optional[int] = 0
    edital: Optional[EditalGeral] = None
    cargos: List[Cargo] = []
