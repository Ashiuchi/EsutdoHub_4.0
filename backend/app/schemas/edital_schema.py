from pydantic import BaseModel, Field
from typing import List, Optional

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
    materias: List[Materia] = Field(description='Lista de matérias exigidas para este cargo específico')

class EditalGeral(BaseModel):
    orgao: str
    banca: str
    data_prova: Optional[str]
    periodo_inscricao: Optional[str]
    link_edital: Optional[str]
    cargos: List[Cargo]
