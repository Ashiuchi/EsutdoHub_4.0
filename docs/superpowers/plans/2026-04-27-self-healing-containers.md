# Self-Healing Containers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar EstudoHub em uma fábrica automática que retoma o trabalho sozinha após qualquer queda, sem reprocessar editais já persistidos no banco.

**Architecture:** Idempotência por `content_hash` direto no banco (sem HTTP intermediário) em dois pontos: o endpoint de upload e o script da moenda. Ambos os scripts de worker viram daemons com `while True` + sleep entre ciclos. Dois novos serviços Docker com `restart: unless-stopped` garantem auto-recuperação.

**Tech Stack:** FastAPI, SQLAlchemy (PostgreSQL), Docker Compose, Python 3.12, pytest, pytest-asyncio

---

## File Map

| Arquivo | Operação | Responsabilidade |
|---|---|---|
| `backend/app/api/endpoints.py` | Modificar | Adicionar check de `content_hash` antes de enfileirar background task |
| `backend/mass_ingestion_industrial.py` | Modificar | Pre-check de hash no banco + daemon loop com sleep de 5 min |
| `backend/scripts/agente_pescador.py` | Modificar | Daemon loop `while True` com sleep de 1h entre ciclos |
| `backend/scripts/Dockerfile.pescador` | Criar | Imagem leve (requests + bs4) para o pescador |
| `docker-compose.yml` | Modificar | Adicionar serviços `moenda` e `pescador` com `restart: unless-stopped` |

---

## Task 1: Idempotência no endpoint de upload

**Files:**
- Modify: `backend/app/api/endpoints.py:116-141`
- Test: `backend/tests/api/test_upload_idempotency.py`

- [ ] **Step 1: Escrever o teste que falha**

Criar `backend/tests/api/test_upload_idempotency.py`:

```python
import uuid
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_upload_returns_existing_edital_when_hash_found():
    """Second upload of same file returns existing edital without queuing a background task."""
    existing_id = uuid.uuid4()
    existing_hash = "a" * 64

    existing = MagicMock()
    existing.id = existing_id
    existing.content_hash = existing_hash
    existing.status = "processado"

    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.return_value = existing

    with patch("app.api.endpoints.SessionLocal", return_value=mock_db), \
         patch("app.api.endpoints._compute_hash", return_value=existing_hash):
        response = client.post(
            "/api/v1/upload",
            files={"file": ("edital.pdf", b"%PDF-1.4 test", "application/pdf")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["content_hash"] == existing_hash
    assert data["status"] == "processado"
    assert str(data["id"]) == str(existing_id)
    # Confirm no temp file was written (background_tasks.add_task not called)
    mock_db.query.assert_called_once()


def test_upload_processes_new_file_when_hash_not_found():
    """Upload of a file not yet in DB queues processing and returns 'processando'."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.return_value = None

    with patch("app.api.endpoints.SessionLocal", return_value=mock_db), \
         patch("app.api.endpoints.PDFService.to_markdown", return_value="# Edital\n"):
        response = client.post(
            "/api/v1/upload",
            files={"file": ("edital.pdf", b"%PDF-1.4 new", "application/pdf")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processando"
```

- [ ] **Step 2: Rodar o teste para confirmar que falha**

```bash
cd /mnt/c/Dev/EstudoHub_4.0/backend
docker compose run --rm backend pytest tests/api/test_upload_idempotency.py -v
```

Esperado: `FAILED` com `AssertionError` pois o endpoint ainda não verifica o banco antes de processar.

- [ ] **Step 3: Implementar o check de idempotência no endpoint**

Em `backend/app/api/endpoints.py`, substituir a função `upload_edital` completa:

```python
@router.post("/upload", response_model=IngestionResponse)
async def upload_edital(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Recebe o arquivo e inicia o processamento em segundo plano.

    Se o content_hash já existir no banco, retorna o edital existente imediatamente
    sem reprocessar. Caso contrário, retorna status 'processando'.
    """
    file_bytes = await file.read()
    content_hash = _compute_hash(file_bytes)

    db = SessionLocal()
    try:
        existing = db.query(models.Edital).filter_by(content_hash=content_hash).first()
        if existing:
            return IngestionResponse(
                id=existing.id,
                content_hash=existing.content_hash,
                status=existing.status,
                total_tables=0,
                total_links=0,
                total_chars=0,
            )
    finally:
        db.close()

    temp_path = f"temp_{content_hash}_{uuid.uuid4().hex[:8]}.pdf"
    async with aiofiles.open(temp_path, "wb") as buffer:
        await buffer.write(file_bytes)

    background_tasks.add_task(_process_edital_task, content_hash, temp_path)

    return IngestionResponse(
        id=uuid.uuid4(),
        content_hash=content_hash,
        status=StatusEdital.PROCESSANDO,
        total_tables=0,
        total_links=0,
        total_chars=0
    )
```

- [ ] **Step 4: Rodar os testes para confirmar que passam**

```bash
cd /mnt/c/Dev/EstudoHub_4.0/backend
docker compose run --rm backend pytest tests/api/test_upload_idempotency.py -v
```

Esperado:
```
PASSED tests/api/test_upload_idempotency.py::test_upload_returns_existing_edital_when_hash_found
PASSED tests/api/test_upload_idempotency.py::test_upload_processes_new_file_when_hash_not_found
```

- [ ] **Step 5: Rodar suite completa para verificar regressões**

```bash
docker compose run --rm backend pytest tests/ -v --ignore=tests/integration
```

Esperado: todos os testes passando.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/endpoints.py backend/tests/api/test_upload_idempotency.py
git commit -m "feat(api): add content_hash idempotency check to upload endpoint"
```

---

## Task 2: Pre-check no banco e daemon mode na Moenda

**Files:**
- Modify: `backend/mass_ingestion_industrial.py`
- Test: `backend/tests/services/test_moenda_daemon.py`

- [ ] **Step 1: Escrever o teste que falha**

Criar `backend/tests/services/test_moenda_daemon.py`:

```python
import asyncio
import hashlib
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from mass_ingestion_industrial import moenda_industrial


@pytest.mark.asyncio
async def test_moenda_skips_pdf_already_in_db(tmp_path):
    """PDFs whose content_hash already exists in DB are skipped without processing."""
    pdf_content = b"%PDF-1.4 fake edital content"
    (tmp_path / "edital_teste.pdf").write_bytes(pdf_content)

    mock_db = MagicMock()
    # DB returns an existing Edital for any hash
    mock_db.query.return_value.filter_by.return_value.first.return_value = MagicMock(id="existing")

    async def mock_sleep(seconds):
        if seconds == 300:
            raise KeyboardInterrupt  # break daemon loop after first cycle

    with patch("mass_ingestion_industrial.STORAGE_SOURCE", tmp_path), \
         patch("mass_ingestion_industrial.SessionLocal", return_value=mock_db), \
         patch("mass_ingestion_industrial.GeometricEngine") as mock_geo, \
         patch("mass_ingestion_industrial.AIService"), \
         patch("mass_ingestion_industrial.SubtractiveAgent"), \
         patch("mass_ingestion_industrial.FingerprintService"), \
         patch("asyncio.sleep", side_effect=mock_sleep):
        with pytest.raises(KeyboardInterrupt):
            await moenda_industrial()

    # Conversion must NOT have been called — PDF was skipped
    mock_geo.return_value.document_to_markdown.assert_not_called()


@pytest.mark.asyncio
async def test_moenda_processes_pdf_not_in_db(tmp_path):
    """PDFs not in DB are processed (GeometricEngine is called)."""
    from unittest.mock import AsyncMock

    pdf_content = b"%PDF-1.4 edital novo"
    (tmp_path / "edital_novo.pdf").write_bytes(pdf_content)

    mock_db = MagicMock()
    # DB returns None — hash not found
    mock_db.query.return_value.filter_by.return_value.first.return_value = None

    async def mock_sleep(seconds):
        if seconds == 300:
            raise KeyboardInterrupt

    mock_geo = MagicMock()
    mock_geo.return_value.document_to_markdown.return_value = "# Edital\n"

    mock_ai = MagicMock()
    mock_ai.return_value.process_edital = AsyncMock(return_value={"id": "novo-id"})

    mock_sub = MagicMock()
    mock_sub.return_value.process.return_value = MagicMock(content_hash=None)

    with patch("mass_ingestion_industrial.STORAGE_SOURCE", tmp_path), \
         patch("mass_ingestion_industrial.SessionLocal", return_value=mock_db), \
         patch("mass_ingestion_industrial.GeometricEngine", mock_geo), \
         patch("mass_ingestion_industrial.AIService", mock_ai), \
         patch("mass_ingestion_industrial.SubtractiveAgent", mock_sub), \
         patch("mass_ingestion_industrial.FingerprintService"), \
         patch("asyncio.sleep", side_effect=mock_sleep):
        with pytest.raises(KeyboardInterrupt):
            await moenda_industrial()

    mock_geo.return_value.document_to_markdown.assert_called_once()
```

- [ ] **Step 2: Rodar o teste para confirmar que falha**

```bash
cd /mnt/c/Dev/EstudoHub_4.0/backend
docker compose run --rm backend pytest tests/services/test_moenda_daemon.py -v
```

Esperado: `FAILED` — a função atual não tem pré-check de DB nem loop daemon.

- [ ] **Step 3: Reescrever `mass_ingestion_industrial.py` com pre-check e daemon loop**

Substituir o conteúdo completo de `backend/mass_ingestion_industrial.py`:

```python
import logging
import sys
import asyncio
import hashlib
from pathlib import Path

from app.services.ai_service import AIService
from app.services.geometric_engine import GeometricEngine
from app.services.subtractive_service import SubtractiveAgent
from app.services.fingerprint_service import FingerprintService
from app.db.database import SessionLocal
from app.db import models

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("storage/industrial_ingestion.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("IndustrialMoenda")

STORAGE_SOURCE = Path("/storage_k")
if not STORAGE_SOURCE.exists():
    STORAGE_SOURCE = Path("sample_editais")


async def moenda_industrial():
    logger.info("🚀 Iniciando Moenda Industrial V4.0 (Daemon Mode)")
    ai_service = AIService()
    geometric = GeometricEngine()
    subtractive = SubtractiveAgent()

    while True:
        files = sorted(list(STORAGE_SOURCE.glob("*.pdf")))
        total = len(files)
        logger.info(f"📂 Escaneando {total} arquivos em {STORAGE_SOURCE}")

        for idx, pdf_path in enumerate(files, 1):
            try:
                pdf_bytes = pdf_path.read_bytes()
                content_hash = hashlib.sha256(pdf_bytes).hexdigest()

                db = SessionLocal()
                try:
                    exists = db.query(models.Edital).filter_by(content_hash=content_hash).first()
                finally:
                    db.close()

                if exists:
                    logger.info(f"⏭️  [{idx}/{total}] Já no banco, pulando: {pdf_path.name}")
                    continue

                logger.info(f"--- [{idx}/{total}] Processando: {pdf_path.name} ---")

                md_content = geometric.document_to_markdown(str(pdf_path))
                fingerprint = FingerprintService.generate_fingerprint(pdf_bytes, md_content)
                trinity = subtractive.process(md_content)
                trinity.content_hash = content_hash
                subtractive.persist(trinity)

                result = await ai_service.process_edital(
                    content_hash=content_hash,
                    md_content=md_content,
                    fingerprint=fingerprint
                )

                if result.get("id"):
                    logger.info(f"✅ Sucesso: Edital ID {result['id']} persistido.")
                else:
                    logger.warning(f"⚠️ Aviso: Edital processado mas ID não retornado.")

                logger.info("💤 Pausa de 10s para resfriamento...")
                await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"❌ Erro crítico no arquivo {pdf_path.name}: {e}")
                continue

        logger.info("💤 Ciclo completo. Aguardando 5 minutos para re-escanear...")
        await asyncio.sleep(300)


if __name__ == "__main__":
    asyncio.run(moenda_industrial())
```

- [ ] **Step 4: Rodar os testes para confirmar que passam**

```bash
cd /mnt/c/Dev/EstudoHub_4.0/backend
docker compose run --rm backend pytest tests/services/test_moenda_daemon.py -v
```

Esperado:
```
PASSED tests/services/test_moenda_daemon.py::test_moenda_skips_pdf_already_in_db
PASSED tests/services/test_moenda_daemon.py::test_moenda_processes_pdf_not_in_db
```

- [ ] **Step 5: Rodar suite completa**

```bash
docker compose run --rm backend pytest tests/ -v --ignore=tests/integration
```

- [ ] **Step 6: Commit**

```bash
git add backend/mass_ingestion_industrial.py backend/tests/services/test_moenda_daemon.py
git commit -m "feat(moenda): add DB pre-check and daemon loop with 5min re-scan interval"
```

---

## Task 3: Daemon loop no Agente Pescador

**Files:**
- Modify: `backend/scripts/agente_pescador.py:218-220`

O loop `while True` é uma mudança estrutural trivial no `__main__` — não há lógica de negócio nova para testar. O comportamento correto é verificado em Task 5 (container sobe e não sai).

- [ ] **Step 1: Substituir o bloco `__main__` do pescador**

Em `backend/scripts/agente_pescador.py`, substituir as últimas 3 linhas:

```python
# ANTES:
if __name__ == "__main__":
    agente = AgentePescador()
    agente.run()
```

Por:

```python
# DEPOIS:
if __name__ == "__main__":
    agente = AgentePescador()
    while True:
        agente.run()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Ciclo completo. Dormindo 1h antes de re-verificar...")
        time.sleep(3600)
```

- [ ] **Step 2: Verificar a sintaxe do arquivo**

```bash
python -c "import ast; ast.parse(open('backend/scripts/agente_pescador.py').read()); print('OK')"
```

Esperado: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/agente_pescador.py
git commit -m "feat(pescador): add daemon loop with 1h interval between scraping cycles"
```

---

## Task 4: Dockerfile.pescador — Imagem leve para o Pescador

**Files:**
- Create: `backend/scripts/Dockerfile.pescador`

- [ ] **Step 1: Criar o Dockerfile**

Criar `backend/scripts/Dockerfile.pescador` com o conteúdo:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir requests beautifulsoup4
COPY agente_pescador.py .
CMD ["python", "-u", "agente_pescador.py"]
```

- [ ] **Step 2: Buildar a imagem para verificar**

```bash
docker build -t estudohub-pescador-test -f backend/scripts/Dockerfile.pescador backend/scripts/
```

Esperado: `Successfully built <image_id>` sem erros.

- [ ] **Step 3: Verificar que as dependências estão disponíveis na imagem**

```bash
docker run --rm estudohub-pescador-test python -c "import requests, bs4; print('deps OK')"
```

Esperado: `deps OK`

- [ ] **Step 4: Limpar a imagem de teste**

```bash
docker rmi estudohub-pescador-test
```

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/Dockerfile.pescador
git commit -m "feat(docker): add lightweight Dockerfile.pescador for web scraper service"
```

---

## Task 5: docker-compose.yml — Serviços moenda e pescador

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Adicionar os dois novos serviços ao docker-compose.yml**

Em `docker-compose.yml`, adicionar antes da seção `volumes:` no final:

```yaml
  moenda:
    build: ./backend
    command: python mass_ingestion_industrial.py
    volumes:
      - ./backend:/app
      - K:\estudohub_storage:/storage_k
      - ./storage:/app/storage
    environment:
      - DATABASE_URL=postgresql://estudohub_admin:estudohub_pass@db:5432/estudohub
    depends_on:
      - db
    restart: unless-stopped

  pescador:
    build:
      context: ./backend/scripts
      dockerfile: Dockerfile.pescador
    volumes:
      - K:\estudohub_storage:/storage_k
      - ./storage:/app/storage
    restart: unless-stopped
```

- [ ] **Step 2: Validar a sintaxe do docker-compose**

```bash
docker compose config --quiet
```

Esperado: sem erros (saída vazia ou apenas a config expandida).

- [ ] **Step 3: Buildar as imagens dos novos serviços**

```bash
docker compose build moenda pescador
```

Esperado: ambas as imagens buildadas sem erros.

- [ ] **Step 4: Subir apenas os novos serviços para verificar inicialização**

```bash
docker compose up -d db
docker compose up moenda --no-deps --timeout 15 &
sleep 8
docker compose logs moenda | head -20
docker compose stop moenda
```

Esperado nos logs:
```
🚀 Iniciando Moenda Industrial V4.0 (Daemon Mode)
📂 Escaneando X arquivos em /storage_k
```

- [ ] **Step 5: Verificar que `restart: unless-stopped` está configurado**

```bash
docker compose config | grep -A2 "restart"
```

Esperado: duas entradas com `restart: unless-stopped` (uma para moenda, uma para pescador).

- [ ] **Step 6: Commit final**

```bash
git add docker-compose.yml
git commit -m "feat(docker): add self-healing moenda and pescador services with restart: unless-stopped"
```

---

## Verificação Final

- [ ] **Subir o stack completo e verificar todos os serviços**

```bash
docker compose up -d
docker compose ps
```

Esperado: todos os serviços com status `Up` ou `Up (healthy)`.

- [ ] **Simular queda e auto-recuperação**

```bash
docker compose kill moenda
sleep 5
docker compose ps moenda
```

Esperado: status `Up` — Docker reiniciou automaticamente.

- [ ] **Verificar logs de idempotência em ação**

```bash
docker compose logs moenda --tail=30
```

Esperado: mensagens `⏭️  Já no banco, pulando:` para PDFs já processados.
