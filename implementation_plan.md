# Plano de Implementação: Edital Verticalizado Elite (Syllabus Architect)

Este plano detalha a transição da extração de matérias para um pipeline de alta fidelidade (10x mais cuidado), utilizando a Abordagem B (1 LLM + Validação Determinística + Refinamento Regex).

## User Review Required

> [!IMPORTANT]
> A implementação exige alterações no schema do banco de dados (SQLAlchemy). Como estamos em ambiente de desenvolvimento, a estratégia padrão será o `create_all`, mas se houver dados críticos, o usuário deve estar ciente da necessidade de reinicializar a tabela `cargos`.

> [!TIP]
> A `CLERK_SECRET_KEY` e outras chaves sensíveis devem ser mantidas exclusivamente no **Vault**. O código de implementação deve refletir isso, buscando as chaves via `config.py`.

## Proposed Changes

### 0. Camada de Infra (Correção de Autenticação)
Para que o Middleware do Next.js (SSR) consiga validar a sessão e o cargo de `admin`, o container do frontend precisa da chave secreta.

#### [MODIFY] [docker-compose.yml](file:///c:/Dev/EstudoHub_4.0/docker-compose.yml)
- Adicionar `CLERK_SECRET_KEY` ao serviço `frontend`.
- Executar `docker-compose up -d frontend` para aplicar.

### 1. Camada de Dados (Schema & DB)
Expandir o modelo de dados para suportar rastreabilidade e métricas de qualidade.

#### [MODIFY] [edital_schema.py](file:///c:/Dev/EstudoHub_4.0/backend/app/schemas/edital_schema.py)
- Adicionar `anchor_text: Optional[str]` ao modelo `Cargo`.
- Adicionar `syllabus_score: Optional[int]` (0-10) ao modelo `Cargo`.

#### [MODIFY] [models.py](file:///c:/Dev/EstudoHub_4.0/backend/app/db/models.py)
- Adicionar coluna `syllabus_score` (Float) e garantir que `anchor_text` (Text) esteja presente na tabela `cargos`.

---

### 2. Camada de Auditoria (SyllabusAuditorAgent)
Novo serviço puro Python para validação e limpeza sem custo de tokens.

#### [NEW] [syllabus_auditor.py](file:///c:/Dev/EstudoHub_4.0/backend/app/services/syllabus_auditor.py)
- **SyllabusAuditorAgent**: Classe que implementa a lógica de score (0-10).
- **SyllabusRefiner**: Métodos Regex para limpar numerações (ex: "1.1.1 Atos" -> "Atos") e normalizar espaços.

---

### 3. Camada de Extração (SubjectsScoutAgent Upgrade)
Evolução do prompt e integração com a auditoria.

#### [MODIFY] [subjects_scout.py](file:///c:/Dev/EstudoHub_4.0/backend/app/services/subjects_scout.py)
- **Prompt Elite**: Reescrita para "Auditor Especialista". Foco em fidelidade absoluta e granularidade.
- **Integração**: No método `scout`, processar as matérias via `auditor.refine()` e `auditor.audit()` antes de retornar.

---

### 4. Orquestração & Resiliência (AIService)
Integração final e persistência.

#### [MODIFY] [ai_service.py](file:///c:/Dev/EstudoHub_4.0/backend/app/services/ai_service.py)
- Atualizar `_persist_cargos_sync` para salvar os novos campos.
- Logar o score de qualidade de forma visível para monitoramento industrial.

### 5. Camada de Inteligência (Canonização Semântica)
Transformar tópicos extraídos em dados canônicos usando Embeddings do Gemini.

#### [MODIFY] [docker-compose.yml](file:///c:/Dev/EstudoHub_4.0/docker-compose.yml)
- Upgrade da imagem do Postgres para `pgvector/pgvector:pg16`.

#### [NEW] [canonicalizer_service.py](file:///c:/Dev/EstudoHub_4.0/backend/app/services/canonicalizer_service.py)
- Serviço para gerar embeddings e realizar busca por similaridade de cosseno (Top-1 nearest neighbor).

## Verification Plan

### Automated Verification
- Execução do pipeline industrial (`mass_ingestion_industrial.py`).
- Verificação visual dos logs buscando os ícones de qualidade (💎, ✅, ⚠️).
- Consulta SQL: `SELECT titulo, syllabus_score FROM cargos;`
