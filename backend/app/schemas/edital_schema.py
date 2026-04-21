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
    vagas_ampla: int
    vagas_cotas: int
    salario: float
    requisitos: str
    status: str = Field(default='extraido', description='Status comercial do cargo')
    price: float = Field(default=0.0, description='Preço de acesso ao conteúdo do cargo')
    materias: List[Materia] = Field(description='Lista de matérias exigidas para este cargo específico')

class EditalGeral(BaseModel):
    orgao: str
    banca: str
    data_prova: Optional[str]
    periodo_inscricao: Optional[str]
    link_edital: Optional[str]
    cargos: List[Cargo]


class EditalResponse(EditalGeral):
    """EditalGeral enriquecido com campos do banco após persistência."""
    id: Optional[uuid.UUID] = None
    status: str = StatusEdital.INGESTADO


class IngestionResponse(BaseModel):
    """Resposta simplificada após a ingestão e persistência do edital."""
    id: uuid.UUID
    content_hash: str
    status: str
    total_tables: int
    total_links: int
    total_chars: int
