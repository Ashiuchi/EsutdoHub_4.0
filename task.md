# Checklist de Tarefas: Edital Verticalizado Elite

Este checklist orienta a execução técnica pelo Claude Code.


- [x] **Tarefa 1: Atualizar Schemas e Modelos**
    - [x] No arquivo `backend/app/schemas/edital_schema.py`, adicione `anchor_text: Optional[str]` e `syllabus_score: Optional[int]` à classe `Cargo`.
    - [x] No arquivo `backend/app/db/models.py`, adicione `syllabus_score = Column(Float, nullable=True)` à classe `Cargo`.

- [x] **Tarefa 2: Implementar SyllabusAuditorAgent**
    - [x] Criar o arquivo `backend/app/services/syllabus_auditor.py` com a lógica de auditoria determinística e refinamento por Regex (limpeza de numeração e lixo de PDF).

- [x] **Tarefa 3: Upgrade no SubjectsScoutAgent**
    - [x] No arquivo `backend/app/services/subjects_scout.py`, atualizar o `_PROMPT_ELITE` para o modo "Auditor Especialista".
    - [x] Integrar o `SyllabusAuditorAgent` no método `scout` para refinar e pontuar as matérias extraídas.

- [x] **Tarefa 4: Orquestração no AIService**
    - [x] No arquivo `backend/app/services/ai_service.py`, atualizar a função `_persist_cargos_sync` para persistir o `anchor_text` e o `syllabus_score`.

- [x] **Tarefa 5: Anchor Coverage Validator**
    - [x] No arquivo `backend/app/services/syllabus_auditor.py`, implementar o método `_check_coverage`.
    - [x] Integrar a validação de cobertura no score final do `audit()`. Punição de -3 pontos por alucinação detectada.

- [ ] **Tarefa 6: Upgrade para pgvector (Infra)**
    - [ ] No arquivo `docker-compose.yml`, mudar imagem do `db` para `pgvector/pgvector:pg16`.
    - [ ] Executar `docker-compose up -d db`.

- [ ] **Tarefa 7: Implementar CanonicalizerService**
    - [ ] Adicionar `pgvector` ao `requirements.txt`.
    - [ ] Criar modelo `CanonicalTopic` no `models.py`.
    - [ ] Criar `app/services/canonicalizer_service.py` com integração ao Gemini `text-embedding-004`.

---

## 🛠️ Instruções Técnicas para Claude Code

### Código para `syllabus_auditor.py`:
```python
import re
from typing import List
from app.schemas.edital_schema import Materia

class SyllabusAuditorAgent:
    def __init__(self):
        self.noise_patterns = [
            re.compile(r"^\d+[\.\)\s\-]+"), 
            re.compile(r"[\s\-\.]{3,}"),
            re.compile(r"p[áa]g\.\s*\d+", re.IGNORECASE)
        ]

    def audit(self, materias: List[Materia], anchor_text_len: int):
        total_topicos = sum(len(m.topicos) for m in materias)
        expected = max(5, anchor_text_len // 300)
        comp = 5 if total_topicos >= expected else 2
        # Retorna score de 0 a 10
        return type('Score', (), {'total': comp + 5, 'verdict': 'bom' if comp > 2 else 'revisar'})

    def refine(self, materia: Materia) -> Materia:
        cleaned = []
        for t in materia.topicos:
            t = re.sub(r"^\d+(\.\d+)*[\s\.\-\)]+", "", t.strip())
            if len(t) > 3: cleaned.append(t)
        return Materia(nome=materia.nome.upper(), topicos=cleaned)

    def _check_coverage(self, materia: Materia, anchor_text: str) -> bool:
        """Verifica se o nome da matéria existe semânticamente no texto original."""
        if not anchor_text: return True
        anchor = re.sub(r'[^a-z0-9]', '', anchor_text.lower())
        m_name = re.sub(r'[^a-z0-9]', '', materia.nome.lower())
        # Se o nome da matéria é curto, busca direto
        if len(m_name) < 10: return m_name in anchor
        # Se longo, busca se ao menos 60% das palavras longas estão lá
        words = [w for w in re.split(r'\s+', materia.nome.lower()) if len(w) > 4]
        if not words: return True
        found = sum(1 for w in words if re.sub(r'[^a-z0-9]', '', w) in anchor)
        return (found / len(words)) >= 0.6

### Código para `canonicalizer_service.py`:
```python
import numpy as np
from pgvector.sqlalchemy import Vector
from sqlalchemy import select, func
from app.db.database import SessionLocal
from app.providers.gemini_provider import GeminiProvider
from app.db.models import CanonicalTopic

class CanonicalizerService:
    def __init__(self):
        self.provider = GeminiProvider()

    async def canonicalize(self, topic_text: str, threshold: float = 0.75):
        embedding = await self.provider.embed_text(topic_text)
        async with SessionLocal() as db:
            # Busca o vizinho mais próximo via similaridade de cosseno (<=> no pgvector)
            query = select(CanonicalTopic).order_by(
                CanonicalTopic.embedding.cosine_distance(embedding)
            ).limit(1)
            result = await db.execute(query)
            match = result.scalar_one_or_none()
            
            if match:
                # Validar se está dentro do threshold (opcional, dependendo do modelo)
                return match.name
            return "Tópico Específico"
```
```
