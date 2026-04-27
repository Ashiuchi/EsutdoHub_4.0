# AI Provider Chain Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the EstudoHub 4.0 AI layer so that Ollama runs as a Docker service, a single provider chain (Ollama → Groq → NVIDIA → OpenRouter → Gemini) is built once in `AIService` and injected into all agents, and `endpoints.py` delegates the full AI pipeline to `AIService.process_edital()`.

**Architecture:** C1 — dependency injection. `AIService._get_provider_chain()` builds the ordered chain and passes it to `CargoTitleAgent`, `CargoVitaminizerAgent`, and `SubjectsScoutAgent` as a parameter. Agents keep all domain logic; the only change is replacing hardcoded `[ollama, gemini]` lists with the injected chain loop.

**Tech Stack:** Python 3.12, FastAPI, Docker Compose, Ollama (ollama/ollama image), pytest + pytest-asyncio, unittest.mock.

---

## File Map

| File | Action | What changes |
|------|--------|--------------|
| `docker-compose.yml` | Modify | Add `ollama` service + `ollama_data` volume + `backend.depends_on` |
| `backend/.env` | Modify | `OLLAMA_URL=http://ollama:11434` |
| `backend/app/services/ai_service.py` | Modify | New `_get_provider_chain()` order; new `process_edital()`; agent instances in `__init__` |
| `backend/app/services/cargo_specialist.py` | Modify | `hunt_titles(chain)`, `_deep_scan(fragment, chain)` — chain loop replaces hardcoded list |
| `backend/app/services/cargo_vitaminizer.py` | Modify | `vitaminize(chain)`, `_discover_structure(chain)`, `_extract_global_metadata(chain)` — loop |
| `backend/app/services/subjects_scout.py` | Modify | `scout(chain)`, `_extract_for_cargo(chain)` — loop replaces single-pick |
| `backend/app/api/endpoints.py` | Modify | Import `AIService`; remove direct agent calls; delegate to `ai_service.process_edital()` |
| `backend/tests/services/test_ai_service_orchestration.py` | Modify | Tests for new `_get_provider_chain()` order and `process_edital()` |
| `backend/tests/services/test_cargo_specialist.py` | Modify | `hunt_titles` / `_deep_scan` tests pass a chain fixture |
| `backend/tests/services/test_cargo_vitaminizer.py` | Modify | Same for vitaminizer methods |
| `backend/tests/services/test_subjects_scout.py` | Modify | Same for scout methods |

---

## Task 1: Infrastructure — Ollama service + OLLAMA_URL

**Files:**
- Modify: `docker-compose.yml`
- Modify: `backend/.env`

- [ ] **Step 1: Add Ollama service to docker-compose.yml**

Open `docker-compose.yml` and apply these changes — add `ollama` service, update `backend.depends_on`, add `ollama_data` to the volumes block:

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: estudohub_admin
      POSTGRES_PASSWORD: dev_secret_vault_99
      POSTGRES_DB: estudohub
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  ollama:
    image: ollama/ollama
    volumes:
      - ollama_data:/root/.ollama
    ports:
      - "11434:11434"

  backend:
    build: ./backend
    volumes:
      - ./backend:/app
    ports:
      - "8000:8000"
    env_file:
      - ./backend/.env
    extra_hosts:
      - "host.docker.internal:host-gateway"
    restart: always
    depends_on:
      - db
      - cache
      - ollama

  frontend:
    build: ./frontend
    volumes:
      - ./frontend:/app
      - /app/node_modules
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://${REMOTE_IP:-localhost}:8000

  cache:
    image: redis:alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
  ollama_data:
```

- [ ] **Step 2: Fix OLLAMA_URL in backend/.env**

Replace line 3 of `backend/.env`:

```
OLLAMA_URL=http://ollama:11434
```

Full `backend/.env` after change:

```
GEMINI_API_KEY=AIzaSyB8XJw2zne7NwwXsGB0ZjnJo2CpVONRkLs
DATABASE_URL=postgresql://estudohub_admin:dev_secret_vault_99@db:5432/estudohub
OLLAMA_URL=http://ollama:11434
LLM_STRATEGY=local_first
CLOUD_FALLBACK=true
OLLAMA_TIMEOUT=120
GEMINI_TIMEOUT=15
```

- [ ] **Step 3: Bring up Ollama and pull the model**

```bash
docker compose up -d ollama
docker exec -it estudohub_40-ollama-1 ollama pull llama3.1:8b
```

Expected: model download progress, ends with `success`.

- [ ] **Step 4: Verify Ollama is reachable**

```bash
curl -s http://localhost:11434/api/tags | python3 -m json.tool
```

Expected: JSON with `"models"` list containing `llama3.1:8b`.

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml backend/.env
git commit -m "feat(infra): add ollama docker service and fix OLLAMA_URL"
```

---

## Task 2: Refactor AIService — new chain order + process_edital()

**Files:**
- Modify: `backend/app/services/ai_service.py`
- Modify: `backend/tests/services/test_ai_service_orchestration.py`

- [ ] **Step 1: Write failing tests for the new chain order and process_edital()**

Replace the contents of `backend/tests/services/test_ai_service_orchestration.py` with:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.ai_service import AIService
from app.providers.base_provider import BaseLLMProvider
from app.schemas.edital_schema import EditalGeral, Cargo, Materia, CargoIdentificado


# ── _get_provider_chain ───────────────────────────────────────────────────────

def test_chain_always_starts_with_ollama():
    service = AIService()
    chain = service._get_provider_chain()
    assert chain[0].__class__.__name__ == "OllamaProvider"


def test_chain_excludes_providers_without_keys(monkeypatch):
    monkeypatch.setattr("app.services.ai_service.settings.groq_api_key", None)
    monkeypatch.setattr("app.services.ai_service.settings.nvidia_api_key", None)
    monkeypatch.setattr("app.services.ai_service.settings.openrouter_api_key", None)
    monkeypatch.setattr("app.services.ai_service.settings.gemini_api_key", None)
    service = AIService()
    chain = service._get_provider_chain()
    assert len(chain) == 1
    assert chain[0].__class__.__name__ == "OllamaProvider"


def test_chain_order_is_ollama_groq_nvidia_openrouter_gemini(monkeypatch):
    monkeypatch.setattr("app.services.ai_service.settings.groq_api_key", "gk-fake")
    monkeypatch.setattr("app.services.ai_service.settings.nvidia_api_key", "nv-fake")
    monkeypatch.setattr("app.services.ai_service.settings.openrouter_api_key", "or-fake")
    monkeypatch.setattr("app.services.ai_service.settings.gemini_api_key", "gem-fake")
    service = AIService()
    chain = service._get_provider_chain()
    names = [p.__class__.__name__ for p in chain]
    assert names == ["OllamaProvider", "GroqProvider", "NVIDIAProvider", "OpenRouterProvider", "GeminiProvider"]


# ── process_edital ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_process_edital_delegates_to_agents():
    service = AIService()
    chain = [MagicMock(spec=BaseLLMProvider)]

    fake_cargos = [CargoIdentificado(titulo="Analista", codigo_edital="01")]
    from app.services.cargo_vitaminizer import VitaminData
    fake_vitamin = VitaminData(
        edital_info=EditalGeral(orgao="Org", banca="Banca"),
        cargos_vitaminados=[Cargo(titulo="Analista")]
    )
    final_cargos = [Cargo(titulo="Analista", materias=[Materia(nome="Math", topicos=["Algebra"])])]

    with patch.object(service, "_get_provider_chain", return_value=chain), \
         patch.object(service.cargo_agent, "hunt_titles", new_callable=AsyncMock, return_value=fake_cargos), \
         patch.object(service.vitaminizer_agent, "vitaminize", new_callable=AsyncMock, return_value=fake_vitamin), \
         patch.object(service.subjects_scout_agent, "scout", new_callable=AsyncMock, return_value=final_cargos):

        result = await service.process_edital("abc123", "markdown content")

    assert result["edital"].orgao == "Org"
    assert len(result["cargos"]) == 1
    service.cargo_agent.hunt_titles.assert_awaited_once_with("abc123", chain)
    service.vitaminizer_agent.vitaminize.assert_awaited_once_with("abc123", fake_cargos, chain)
    service.subjects_scout_agent.scout.assert_awaited_once_with("abc123", fake_vitamin.cargos_vitaminados, chain)


@pytest.mark.asyncio
async def test_process_edital_returns_empty_cargos_when_all_fail():
    service = AIService()
    from app.services.cargo_vitaminizer import VitaminData
    fake_vitamin = VitaminData(
        edital_info=EditalGeral(orgao="Org", banca="Banca"),
        cargos_vitaminados=[]
    )
    with patch.object(service, "_get_provider_chain", return_value=[]), \
         patch.object(service.cargo_agent, "hunt_titles", new_callable=AsyncMock, return_value=[]), \
         patch.object(service.vitaminizer_agent, "vitaminize", new_callable=AsyncMock, return_value=fake_vitamin), \
         patch.object(service.subjects_scout_agent, "scout", new_callable=AsyncMock, return_value=[]):

        result = await service.process_edital("abc123", "markdown content")

    assert result["cargos"] == []
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /mnt/c/Dev/EstudoHub_4.0/backend
python -m pytest tests/services/test_ai_service_orchestration.py -v 2>&1 | tail -20
```

Expected: multiple FAILED — `process_edital` not defined, chain order wrong.

- [ ] **Step 3: Rewrite ai_service.py**

Replace the full contents of `backend/app/services/ai_service.py`:

```python
import asyncio
import logging
from typing import List, Optional, Set

from app.core.config import settings
from app.core.logging_streamer import log_streamer
from app.db import models as db_models
from app.db.database import SessionLocal
from app.providers.base_provider import BaseLLMProvider
from app.providers.gemini_provider import GeminiProvider
from app.providers.ollama_provider import OllamaProvider
from app.providers.groq_provider import GroqProvider
from app.providers.openrouter_provider import OpenRouterProvider
from app.providers.nvidia_provider import NVIDIAProvider
from app.schemas.edital_schema import Cargo, EditalGeral, EditalResponse, Materia, StatusEdital
from app.services.chunker_service import MarkdownChunker
from app.services.cargo_specialist import CargoTitleAgent
from app.services.cargo_vitaminizer import CargoVitaminizerAgent
from app.services.subjects_scout import SubjectsScoutAgent

logger = logging.getLogger(__name__)

CHUNK_THRESHOLD = 15_000
CHUNK_SIZE = 15_000
CHUNK_OVERLAP = 1_000


class AIService:
    """Orquestra provider chain, pipeline de agentes e persistência incremental."""

    def __init__(self) -> None:
        self.ollama_provider = OllamaProvider()
        self.groq_provider = GroqProvider()
        self.nvidia_provider = NVIDIAProvider()
        self.openrouter_provider = OpenRouterProvider()
        self.gemini_provider = GeminiProvider()

        self.cargo_agent = CargoTitleAgent()
        self.vitaminizer_agent = CargoVitaminizerAgent()
        self.subjects_scout_agent = SubjectsScoutAgent()

        chain_names = [p.__class__.__name__ for p in self._get_provider_chain()]
        logger.info("AIService initialized — chain: %s", " → ".join(chain_names))

    # ------------------------------------------------------------------ #
    #  Provider chain                                                       #
    # ------------------------------------------------------------------ #

    def _get_provider_chain(self) -> List[BaseLLMProvider]:
        """Constrói lista ordenada: Ollama sempre primeiro, cloud providers se tiverem chave."""
        chain: List[BaseLLMProvider] = [self.ollama_provider]

        if settings.groq_api_key:
            chain.append(self.groq_provider)
        if settings.nvidia_api_key:
            chain.append(self.nvidia_provider)
        if settings.openrouter_api_key:
            chain.append(self.openrouter_provider)
        if settings.gemini_api_key:
            chain.append(self.gemini_provider)

        if len(chain) == 1:
            logger.warning("Nenhuma chave cloud configurada — chain usa apenas Ollama.")

        return chain

    # ------------------------------------------------------------------ #
    #  Pipeline entry point                                                 #
    # ------------------------------------------------------------------ #

    async def process_edital(self, content_hash: str, md_content: str) -> dict:
        """Orquestra CargoTitleAgent → CargoVitaminizerAgent → SubjectsScoutAgent.

        Injeta a chain de providers em cada agente.
        Retorna dict com 'edital' (EditalGeral) e 'cargos' (List[Cargo]).
        """
        chain = self._get_provider_chain()
        logger.info(
            "process_edital [%s]: chain=[%s]",
            content_hash[:12],
            ", ".join(p.__class__.__name__ for p in chain),
        )

        cargos = await self.cargo_agent.hunt_titles(content_hash, chain)
        vitamin_data = await self.vitaminizer_agent.vitaminize(content_hash, cargos, chain)
        cargos_com_materias = await self.subjects_scout_agent.scout(
            content_hash, vitamin_data.cargos_vitaminados, chain
        )

        return {"edital": vitamin_data.edital_info, "cargos": cargos_com_materias}

    # ------------------------------------------------------------------ #
    #  LLM extraction (kept for backwards-compat / direct chunk use)       #
    # ------------------------------------------------------------------ #

    async def _extract_from_chunk(self, chunk: str) -> Optional[EditalGeral]:
        prompt = f'''
        Analise o edital abaixo e extraia os dados estruturados.
        Foque especialmente na separação por CARGOS. Cada cargo deve ter suas matérias e requisitos.
        Retorne APENAS o JSON puro seguindo este schema:
        {EditalGeral.model_json_schema()}

        EDITAL EM MARKDOWN:
        {chunk}
        '''
        for provider in self._get_provider_chain():
            try:
                logger.info("Tentando provider %s...", provider.__class__.__name__)
                log_streamer.broadcast({"type": "log", "message": f"🤖 IA: Tentando extração com {provider.__class__.__name__}...", "level": "INFO"})
                result: EditalGeral = await provider.generate_json(prompt=prompt, schema=EditalGeral)
                logger.info("Provider %s respondeu com sucesso.", provider.__class__.__name__)
                return result
            except Exception as e:
                logger.warning("⚠️ %s falhou, tentando próximo: %s", provider.__class__.__name__, e)
                log_streamer.broadcast({"type": "log", "message": f"⚠️ {provider.__class__.__name__} falhou, tentando próximo...", "level": "WARNING"})
        return None

    # ------------------------------------------------------------------ #
    #  Merge helpers                                                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _merge_materias(existing: List[Materia], incoming: List[Materia]) -> List[Materia]:
        seen = {m.nome: m for m in existing}
        for m in incoming:
            if m.nome not in seen:
                seen[m.nome] = m
        return list(seen.values())

    @staticmethod
    def _merge_cargos(base: List[Cargo], incoming: List[Cargo]) -> List[Cargo]:
        index = {c.titulo: c for c in base}
        for cargo in incoming:
            if cargo.titulo in index:
                merged = AIService._merge_materias(index[cargo.titulo].materias, cargo.materias)
                index[cargo.titulo] = index[cargo.titulo].model_copy(update={"materias": merged})
            else:
                index[cargo.titulo] = cargo
        return list(index.values())

    # ------------------------------------------------------------------ #
    #  Database persistence                                                 #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _create_edital_sync(result: EditalGeral) -> Optional[int]:
        db = SessionLocal()
        try:
            edital_db = db_models.Edital(
                orgao=result.orgao,
                banca=result.banca,
                data_prova=result.data_prova,
                link=result.link_edital,
                status=StatusEdital.INGESTADO,
            )
            db.add(edital_db)
            db.commit()
            db.refresh(edital_db)
            logger.info("Edital '%s' criado no banco (id=%s).", result.orgao, edital_db.id)
            return edital_db.id
        except Exception as e:
            logger.error("Falha ao criar Edital no banco: %s", e)
            db.rollback()
            return None
        finally:
            db.close()

    @staticmethod
    def _persist_cargos_sync(edital_db_id: int, cargos: List[Cargo], known_titulos: Set[str]) -> List[dict]:
        saved: List[dict] = []
        db = SessionLocal()
        try:
            for cargo_schema in cargos:
                if cargo_schema.titulo in known_titulos:
                    continue
                cargo_db = db_models.Cargo(
                    edital_id=edital_db_id,
                    titulo=cargo_schema.titulo,
                    salario=cargo_schema.salario,
                    requisitos=cargo_schema.requisitos,
                    status="extraido",
                    price=0.0,
                )
                db.add(cargo_db)
                db.flush()
                for materia_schema in cargo_schema.materias:
                    materia_db = db_models.Materia(cargo_id=cargo_db.id, nome=materia_schema.nome)
                    db.add(materia_db)
                    db.flush()
                    for topico_str in materia_schema.topicos:
                        db.add(db_models.Topico(materia_id=materia_db.id, conteudo=topico_str))
                db.commit()
                known_titulos.add(cargo_schema.titulo)
                saved.append(cargo_schema.model_dump())
        except Exception as e:
            logger.error("Falha ao persistir cargos (edital_id=%s): %s", edital_db_id, e)
            db.rollback()
        finally:
            db.close()
        return saved

    async def _create_edital_db(self, result: EditalGeral) -> Optional[int]:
        return await asyncio.to_thread(self._create_edital_sync, result)

    async def _persist_and_broadcast(self, edital_db_id: int, cargos: List[Cargo], known_titulos: Set[str]) -> None:
        saved = await asyncio.to_thread(self._persist_cargos_sync, edital_db_id, cargos, known_titulos)
        for cargo_dict in saved:
            logger.info("Cargo '%s' extraído e salvo!", cargo_dict["titulo"])
            log_streamer.broadcast({"type": "data", "payload": cargo_dict})

    # ------------------------------------------------------------------ #
    #  Legacy chunked extraction (kept for backwards-compat)               #
    # ------------------------------------------------------------------ #

    async def extract_edital_data(self, md_content: str) -> EditalResponse:
        if len(md_content) <= CHUNK_THRESHOLD:
            logger.info("Edital pequeno (%d chars) — processamento direto.", len(md_content))
            result = await self._extract_from_chunk(md_content)
            if result is None:
                raise RuntimeError("Todos os providers LLM falharam na extração.")
            edital_db_id = await self._create_edital_db(result)
            if edital_db_id:
                await self._persist_and_broadcast(edital_db_id, result.cargos, set())
            return EditalResponse(**result.model_dump(), id=edital_db_id, status=StatusEdital.INGESTADO)

        chunker = MarkdownChunker(chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
        chunks = chunker.split(md_content)
        total = len(chunks)
        logger.info("Edital grande (%d chars) dividido em %d chunks.", len(md_content), total)

        merged: Optional[EditalGeral] = None
        edital_db_id: Optional[int] = None
        known_titulos: Set[str] = set()
        failed_chunks: List[int] = []

        for idx, chunk in enumerate(chunks, start=1):
            logger.info("Processando chunk %d/%d (%d chars)...", idx, total, len(chunk))
            result = await self._extract_from_chunk(chunk)
            await asyncio.sleep(2.0)

            if result is None:
                logger.warning("Chunk %d/%d falhou — pulando.", idx, total)
                failed_chunks.append(idx)
                continue

            if merged is None:
                merged = result
                edital_db_id = await self._create_edital_db(result)
                if edital_db_id:
                    await self._persist_and_broadcast(edital_db_id, result.cargos, known_titulos)
            else:
                new_cargos = [c for c in result.cargos if c.titulo not in known_titulos]
                if edital_db_id and new_cargos:
                    await self._persist_and_broadcast(edital_db_id, new_cargos, known_titulos)
                merged_cargos = self._merge_cargos(merged.cargos, result.cargos)
                merged = merged.model_copy(update={"cargos": merged_cargos})

        if merged is None or not merged.cargos:
            raise RuntimeError(f"Extração em chunks não produziu cargos. Chunks falhos: {failed_chunks}/{total}")

        if failed_chunks:
            logger.warning("Extração concluída com %d chunk(s) falho(s): %s", len(failed_chunks), failed_chunks)

        return EditalResponse(**merged.model_dump(), id=edital_db_id, status=StatusEdital.INGESTADO)
```

- [ ] **Step 4: Run tests — expect pass**

```bash
cd /mnt/c/Dev/EstudoHub_4.0/backend
python -m pytest tests/services/test_ai_service_orchestration.py -v 2>&1 | tail -20
```

Expected: all tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai_service.py backend/tests/services/test_ai_service_orchestration.py
git commit -m "feat(ai): refactor provider chain order and add process_edital orchestrator"
```

---

## Task 3: Inject chain into CargoTitleAgent

**Files:**
- Modify: `backend/app/services/cargo_specialist.py`
- Modify: `backend/tests/services/test_cargo_specialist.py`

- [ ] **Step 1: Write failing tests for the new signatures**

Append these tests to `backend/tests/services/test_cargo_specialist.py`:

```python
# ── chain injection ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_deep_scan_uses_first_working_provider_in_chain(tmp_path):
    agent = CargoTitleAgent()
    from app.providers.base_provider import BaseLLMProvider
    from app.schemas.edital_schema import CargoIdentificado

    failing = MagicMock(spec=BaseLLMProvider)
    failing.generate_json = AsyncMock(side_effect=ConnectionError("down"))

    working = MagicMock(spec=BaseLLMProvider)
    from pydantic import BaseModel
    class CargoList(BaseModel):
        cargos: list[CargoIdentificado]
    working.generate_json = AsyncMock(return_value=CargoList(
        cargos=[CargoIdentificado(titulo="Analista", codigo_edital="01")]
    ))

    chain = [failing, working]
    result = await agent._deep_scan("fragmento de edital", chain)

    assert len(result) == 1
    assert result[0].titulo == "Analista"
    failing.generate_json.assert_awaited_once()
    working.generate_json.assert_awaited_once()


@pytest.mark.asyncio
async def test_deep_scan_returns_empty_when_all_providers_fail():
    agent = CargoTitleAgent()
    from app.providers.base_provider import BaseLLMProvider

    bad = MagicMock(spec=BaseLLMProvider)
    bad.generate_json = AsyncMock(side_effect=Exception("fail"))

    result = await agent._deep_scan("fragmento", [bad, bad])
    assert result == []


@pytest.mark.asyncio
async def test_hunt_titles_passes_chain_to_deep_scan(tmp_path):
    agent = CargoTitleAgent()
    from app.providers.base_provider import BaseLLMProvider
    chain = [MagicMock(spec=BaseLLMProvider)]

    storage = tmp_path / "storage" / "processed" / "abc123"
    storage.mkdir(parents=True)
    (storage / "main.md").write_text("Cargo Analista Vagas 10 Jornada 40h " * 20)

    with patch.object(agent, "_deep_scan", new_callable=AsyncMock, return_value=[]) as mock_ds, \
         patch("app.services.cargo_specialist.Path", side_effect=lambda *a: tmp_path.joinpath(*a)):
        await agent.hunt_titles("abc123", chain)

    for call in mock_ds.call_args_list:
        assert call.args[1] is chain or call.kwargs.get("chain") is chain
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /mnt/c/Dev/EstudoHub_4.0/backend
python -m pytest tests/services/test_cargo_specialist.py::test_deep_scan_uses_first_working_provider_in_chain tests/services/test_cargo_specialist.py::test_deep_scan_returns_empty_when_all_providers_fail -v 2>&1 | tail -15
```

Expected: FAILED — `_deep_scan()` missing `chain` argument.

- [ ] **Step 3: Rewrite cargo_specialist.py**

Replace the full contents of `backend/app/services/cargo_specialist.py`:

```python
import re
import json
import logging
import asyncio
from pathlib import Path
from typing import List, Dict

import pandas as pd
import io
from pydantic import BaseModel

from app.providers.base_provider import BaseLLMProvider
from app.schemas.edital_schema import CargoIdentificado
from app.core.logging_streamer import log_streamer

logger = logging.getLogger(__name__)


class CargoTitleAgent:
    def __init__(self):
        self.semaphore = asyncio.Semaphore(3)
        self.anchors = [
            r"Cód\.", r"Cargo", r"Função", r"Vagas", r"AC/PCD",
            r"Nível Superior", r"Nível Médio", r"Especialidade", r"Jornada"
        ]
        self.anchor_re = re.compile("|".join(self.anchors), re.IGNORECASE)

    def _identify_relevant_chunks(self, md_content: str) -> List[str]:
        window_size = 3000
        overlap = 500
        chunks = []

        if len(md_content) <= window_size:
            chunks = [md_content]
        else:
            for i in range(0, len(md_content), window_size - overlap):
                chunk = md_content[i:i + window_size]
                chunks.append(chunk)
                if i + window_size >= len(md_content):
                    break

        scored_chunks = []
        for chunk in chunks:
            score = len(self.anchor_re.findall(chunk))
            score += chunk.lower().count("vagas") * 0.5
            score += chunk.lower().count("jornada") * 0.5
            score += chunk.lower().count("remuneração") * 0.5
            scored_chunks.append((score, chunk))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        return [chunk for score, chunk in scored_chunks[:3] if score > 0]

    async def hunt_titles(self, content_hash: str, chain: List[BaseLLMProvider]) -> List[CargoIdentificado]:
        """Identifica todos os títulos e códigos de cargos como instâncias únicas."""
        storage_path = Path("storage/processed") / content_hash
        tables_dir = storage_path / "tables"
        main_md_path = storage_path / "main.md"

        all_cargos: Dict[str, CargoIdentificado] = {}

        def _add_cargo(cargo: CargoIdentificado):
            key = f"{cargo.codigo_edital}_{cargo.titulo}" if cargo.codigo_edital else cargo.titulo
            if key not in all_cargos:
                all_cargos[key] = cargo
                log_streamer.broadcast({
                    "type": "data",
                    "payload": {
                        "titulo": cargo.titulo,
                        "codigo_edital": cargo.codigo_edital,
                        "status": "identificado",
                        "vagas_ac": 0, "vagas_cr": 0, "vagas_total": 0, "salario": 0, "materias": []
                    }
                })

        if main_md_path.exists():
            main_content = main_md_path.read_text(encoding="utf-8")
            log_streamer.broadcast({"type": "log", "message": "📡 CargoTitleAgent: Ativando Radar de Relevância no texto principal...", "level": "INFO"})
            relevant_chunks = self._identify_relevant_chunks(main_content)

            async def _process_chunk(chunk: str, idx: int):
                log_streamer.broadcast({"type": "log", "message": f"🔍 Analisando Bloco Relevante {idx+1}/{len(relevant_chunks)}...", "level": "INFO"})
                found_cargos = await self._deep_scan(chunk, chain)
                for cargo in found_cargos:
                    _add_cargo(cargo)

            if relevant_chunks:
                await asyncio.gather(*[_process_chunk(c, i) for i, c in enumerate(relevant_chunks)])

        if tables_dir.exists():
            table_files = sorted(list(tables_dir.glob("*.md")))
            log_streamer.broadcast({"type": "log", "message": f"🔍 CargoTitleAgent: Analisando {len(table_files)} tabelas...", "level": "INFO"})

            async def _process_table_file(table_file: Path):
                table_content = table_file.read_text(encoding="utf-8")
                found_cargos = []
                if self.anchor_re.search(table_content):
                    logger.info("Sprint Scan: Âncoras encontradas em %s.", table_file.name)
                    found_cargos = self._sprint_scan(table_content)
                    if not found_cargos:
                        logger.info("Sprint Scan inconclusivo em %s. Acionando Deep Scan.", table_file.name)
                        found_cargos = await self._deep_scan(table_content, chain)
                else:
                    if any(kw in table_content.lower() for kw in ["vagas", "remuneração", "vencimento", "salário"]):
                        logger.info("Tabela %s sem âncoras claras mas relevante. Deep Scan.", table_file.name)
                        found_cargos = await self._deep_scan(table_content, chain)
                for cargo in found_cargos:
                    _add_cargo(cargo)

            if table_files:
                await asyncio.gather(*[_process_table_file(f) for f in table_files])
        else:
            logger.warning("Diretório de tabelas não encontrado: %s", tables_dir)

        result_list = list(all_cargos.values())
        log_streamer.broadcast({"type": "log", "message": f"✅ CargoTitleAgent: {len(result_list)} cargos identificados.", "level": "INFO"})
        return result_list

    def _sprint_scan(self, table_content: str) -> List[CargoIdentificado]:
        try:
            lines = [l.strip() for l in table_content.strip().splitlines() if l.strip()]
            if len(lines) < 3:
                return []
            content_lines = [l for l in lines if not all(c in '|- : \t' for c in l)]
            df = pd.read_csv(
                io.StringIO('\n'.join(content_lines)),
                sep='|',
                skipinitialspace=True
            ).loc[:, ~pd.Series([True]*0)]
            df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
            df.columns = [c.strip() for c in df.columns]

            col_cargo = None
            col_codigo = None
            for col in df.columns:
                col_lower = col.lower()
                if any(x in col_lower for x in ["cargo", "função", "denominação"]):
                    col_cargo = col
                if any(x in col_lower for x in ["cód", "codigo", "item"]):
                    col_codigo = col

            if not col_cargo:
                return []

            cargos = []
            for _, row in df.iterrows():
                titulo = str(row[col_cargo]).strip()
                if not titulo or titulo.lower() in ["nan", "none", ""]:
                    continue
                codigo = str(row[col_codigo]).strip() if col_codigo else None
                if codigo and codigo.lower() in ["nan", "none", ""]:
                    codigo = None
                cargos.append(CargoIdentificado(titulo=titulo, codigo_edital=codigo))
            return cargos
        except Exception as e:
            logger.warning("Sprint Scan falhou: %s", e)
            return []

    async def _deep_scan(self, fragment: str, chain: List[BaseLLMProvider]) -> List[CargoIdentificado]:
        """Usa a chain de providers para extrair cargos de fragmentos complexos."""
        async with self.semaphore:
            prompt = f"""
            Analise o fragmento abaixo extraído de um edital de concurso.
            Identifique e extraia TODOS os cargos e seus respectivos códigos (se houver).

            REGRAS CRÍTICAS:
            1. Combine cargo e especialidade no título (ex: "Cargo - Área").
            2. Extraia o código se disponível.
            3. Retorne APENAS um JSON: {{"cargos": [{{"titulo": "NOME DO CARGO", "codigo_edital": "CÓDIGO"}}, ...]}}

            FRAGMENTO:
            {fragment}
            """

            class CargoList(BaseModel):
                cargos: List[CargoIdentificado]

            for provider in chain:
                try:
                    result: CargoList = await provider.generate_json(prompt=prompt, schema=CargoList)
                    return result.cargos
                except Exception as e:
                    logger.warning("⚠️ %s falhou, tentando próximo: %s", provider.__class__.__name__, e)
                    continue

            logger.error("Todos os providers falharam em _deep_scan.")
            return []
```

- [ ] **Step 4: Run all cargo_specialist tests**

```bash
cd /mnt/c/Dev/EstudoHub_4.0/backend
python -m pytest tests/services/test_cargo_specialist.py -v 2>&1 | tail -25
```

Expected: all PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/cargo_specialist.py backend/tests/services/test_cargo_specialist.py
git commit -m "feat(agents): inject provider chain into CargoTitleAgent"
```

---

## Task 4: Inject chain into CargoVitaminizerAgent

**Files:**
- Modify: `backend/app/services/cargo_vitaminizer.py`
- Modify: `backend/tests/services/test_cargo_vitaminizer.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/services/test_cargo_vitaminizer.py`:

```python
# ── chain injection ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_discover_structure_falls_back_to_second_provider():
    from app.services.cargo_vitaminizer import CargoVitaminizerAgent, MappingDiscovery
    from app.providers.base_provider import BaseLLMProvider

    agent = CargoVitaminizerAgent()

    failing = MagicMock(spec=BaseLLMProvider)
    failing.generate_json = AsyncMock(side_effect=ConnectionError("down"))

    working = MagicMock(spec=BaseLLMProvider)
    working.generate_json = AsyncMock(return_value=MappingDiscovery(
        acronyms={"AC": "vagas_ac"},
        regions={},
        headers=["Cargo"]
    ))

    chain = [failing, working]
    result = await agent._discover_structure("texto", [], chain)

    assert result.acronyms == {"AC": "vagas_ac"}
    failing.generate_json.assert_awaited_once()
    working.generate_json.assert_awaited_once()


@pytest.mark.asyncio
async def test_extract_global_metadata_falls_back_to_second_provider():
    from app.services.cargo_vitaminizer import CargoVitaminizerAgent, GlobalMetadata
    from app.providers.base_provider import BaseLLMProvider
    from app.schemas.edital_schema import EditalGeral

    agent = CargoVitaminizerAgent()

    failing = MagicMock(spec=BaseLLMProvider)
    failing.generate_json = AsyncMock(side_effect=Exception("quota"))

    working = MagicMock(spec=BaseLLMProvider)
    working.generate_json = AsyncMock(return_value=GlobalMetadata(
        edital_info=EditalGeral(orgao="Banco X", banca="Cesgranrio"),
        salary_patterns=["R$ 4.000,00"]
    ))

    chain = [failing, working]
    result = await agent._extract_global_metadata("texto", chain)

    assert result.edital_info.orgao == "Banco X"
    failing.generate_json.assert_awaited_once()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /mnt/c/Dev/EstudoHub_4.0/backend
python -m pytest tests/services/test_cargo_vitaminizer.py::test_discover_structure_falls_back_to_second_provider tests/services/test_cargo_vitaminizer.py::test_extract_global_metadata_falls_back_to_second_provider -v 2>&1 | tail -15
```

Expected: FAILED — methods missing `chain` argument.

- [ ] **Step 3: Rewrite cargo_vitaminizer.py**

Replace the full contents of `backend/app/services/cargo_vitaminizer.py`:

```python
import re
import logging
import pandas as pd
import io
import asyncio
from pathlib import Path
from typing import List, Dict

from pydantic import BaseModel

from app.providers.base_provider import BaseLLMProvider
from app.schemas.edital_schema import Cargo, EditalGeral, CargoIdentificado
from app.core.logging_streamer import log_streamer

logger = logging.getLogger(__name__)


class MappingDiscovery(BaseModel):
    acronyms: Dict[str, str]
    regions: Dict[str, str]
    headers: List[str]


class GlobalMetadata(BaseModel):
    edital_info: EditalGeral
    salary_patterns: List[str]


class VitaminData(BaseModel):
    edital_info: EditalGeral
    cargos_vitaminados: List[Cargo]


class CargoVitaminizerAgent:
    def __init__(self):
        self.semaphore = asyncio.Semaphore(3)

    async def _discover_structure(self, main_md: str, tables: List[str], chain: List[BaseLLMProvider]) -> MappingDiscovery:
        async with self.semaphore:
            log_streamer.broadcast({"type": "log", "message": "🔍 Analisando legendas e estruturas dinâmicas...", "level": "INFO"})
            headers_sample = [t.splitlines()[0] for t in tables[:15] if "|" in t]
            prompt = f"""
            Analise o texto e os cabeçalhos das tabelas de um edital.
            Identifique o significado de siglas de vagas e mapeamentos de códigos/regiões para cargos.

            TEXTO (FRAGMENTO):
            {main_md[:5000]}

            CABEÇALHOS DE TABELAS:
            {headers_sample}

            Retorne um JSON:
            {{
                "acronyms": {{ "SIGLA": "campo_pydantic" }},
                "regions": {{ "CÓDIGO": "NOME DO CARGO" }},
                "headers": ["Nomes de colunas de cargo"]
            }}

            CAMPOS VÁLIDOS: vagas_ac, vagas_pcd, vagas_negros, vagas_indigenas, vagas_trans, vagas_cr, vagas_total.
            """

            for provider in chain:
                try:
                    mapping = await provider.generate_json(prompt=prompt, schema=MappingDiscovery)
                    for sigla, campo in mapping.acronyms.items():
                        log_streamer.broadcast({"type": "log", "message": f"📌 Legenda descoberta: {sigla} -> {campo}", "level": "INFO"})
                    for cod, cargo in mapping.regions.items():
                        log_streamer.broadcast({"type": "log", "message": f"📌 Mapeamento descoberto: {cod} -> {cargo}", "level": "INFO"})
                    return mapping
                except Exception as e:
                    logger.warning("⚠️ %s falhou, tentando próximo: %s", provider.__class__.__name__, e)
                    continue

            logger.error("Todos os providers falharam em _discover_structure.")
            return MappingDiscovery(acronyms={}, regions={}, headers=[])

    def _process_single_table(self, table_md: str, discovery: MappingDiscovery, identified_cargos: List[CargoIdentificado], cargo_totals: Dict[str, Dict[str, int]]):
        try:
            lines = [l.strip() for l in table_md.splitlines() if "|" in l]
            if len(lines) < 3:
                return
            clean_lines = [lines[0]] + [l for l in lines[1:] if not all(c in "|- : \t" for c in l)]
            df = pd.read_csv(io.StringIO("\n".join(clean_lines)), sep="|").loc[:, ~pd.Series([True]*0)]
            df.columns = [c.strip() for c in df.columns]

            for _, row in df.iterrows():
                row_str = " ".join(str(v) for v in row.values)
                target_cargo = None
                for code, name in discovery.regions.items():
                    if code in row_str:
                        target_cargo = next((c.titulo for c in identified_cargos if name.lower() in c.titulo.lower()), None)
                        break
                if not target_cargo:
                    for c in identified_cargos:
                        if c.titulo.lower() in row_str.lower():
                            target_cargo = c.titulo
                            break

                if target_cargo and target_cargo in cargo_totals:
                    for sigla, field in discovery.acronyms.items():
                        for col in df.columns:
                            if sigla.lower() == col.lower():
                                val = str(row[col]).strip()
                                nums = re.findall(r"\d+", val)
                                if nums:
                                    cargo_totals[target_cargo][field] += int(nums[0])
        except Exception as e:
            logger.warning("Erro ao processar tabela: %s", e)

    def _aggregate_vacancies(self, tables: List[str], discovery: MappingDiscovery, identified_cargos: List[CargoIdentificado]) -> Dict[str, Dict[str, int]]:
        cargo_totals = {
            c.titulo: {f: 0 for f in ["vagas_ac", "vagas_pcd", "vagas_negros", "vagas_indigenas", "vagas_trans", "vagas_cr", "vagas_total"]}
            for c in identified_cargos
        }
        for table_md in tables:
            self._process_single_table(table_md, discovery, identified_cargos, cargo_totals)
        return cargo_totals

    async def _extract_global_metadata(self, main_md: str, chain: List[BaseLLMProvider]) -> GlobalMetadata:
        async with self.semaphore:
            prompt = f"Extraia metadados globais do edital em JSON (EditalGeral + salary_patterns como lista de strings).\nTEXTO: {main_md[:5000]}"

            for provider in chain:
                try:
                    return await provider.generate_json(prompt=prompt, schema=GlobalMetadata)
                except Exception as e:
                    logger.warning("⚠️ %s falhou, tentando próximo: %s", provider.__class__.__name__, e)
                    continue

            logger.error("Todos os providers falharam em _extract_global_metadata.")
            return GlobalMetadata(
                edital_info=EditalGeral(orgao="Pendente", banca="Pendente"),
                salary_patterns=[]
            )

    async def vitaminize(self, content_hash: str, identified_cargos: List[CargoIdentificado], chain: List[BaseLLMProvider]) -> VitaminData:
        storage_path = Path("backend/storage/processed") / content_hash
        if not storage_path.exists():
            storage_path = Path("storage/processed") / content_hash

        main_md = (storage_path / "main.md").read_text(encoding="utf-8") if (storage_path / "main.md").exists() else ""
        table_files = sorted((storage_path / "tables").glob("*.md")) if (storage_path / "tables").exists() else []
        tables = [f.read_text(encoding="utf-8") for f in table_files]

        log_streamer.broadcast({"type": "log", "message": "📡 Iniciando Vitaminização V3.1 (Agnóstica)...", "level": "INFO"})

        ruido = ["jurado", "redator", "espectro", "deficiência", "negros", "total", "nenhum", "cargo", "área"]
        identified_cargos = [c for c in identified_cargos if not any(r in c.titulo.lower() for r in ruido)]

        discovery = await self._discover_structure(main_md, tables, chain)
        vagas_agregadas = self._aggregate_vacancies(tables, discovery, identified_cargos)
        metadata = await self._extract_global_metadata(main_md, chain)

        cargos_finais = []
        for cargo_id in identified_cargos:
            v_data = vagas_agregadas.get(cargo_id.titulo, {})
            sal_str = metadata.salary_patterns[0] if metadata.salary_patterns else "0"
            salario = float(re.sub(r"[^\d.]", "", sal_str.replace(".", "").replace(",", "."))) if sal_str else 0.0

            cargo_vitaminado = Cargo(
                titulo=cargo_id.titulo,
                vagas_ac=v_data.get("vagas_ac", 0),
                vagas_pcd=v_data.get("vagas_pcd", 0),
                vagas_cr=v_data.get("vagas_cr", 0),
                vagas_negros=v_data.get("vagas_negros", 0),
                vagas_total=v_data.get("vagas_total", 0) or sum(v for k, v in v_data.items() if "total" not in k),
                salario=salario,
                status="vitaminado"
            )
            cargos_finais.append(cargo_vitaminado)
            log_streamer.broadcast({"type": "data", "payload": cargo_vitaminado.model_dump()})
            log_streamer.broadcast({"type": "log", "message": f"✅ Cargo vitaminado: {cargo_vitaminado.titulo} ({cargo_vitaminado.vagas_total} vagas)", "level": "INFO"})

        return VitaminData(edital_info=metadata.edital_info, cargos_vitaminados=cargos_finais)
```

- [ ] **Step 4: Run all cargo_vitaminizer tests**

```bash
cd /mnt/c/Dev/EstudoHub_4.0/backend
python -m pytest tests/services/test_cargo_vitaminizer.py -v 2>&1 | tail -25
```

Expected: all PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/cargo_vitaminizer.py backend/tests/services/test_cargo_vitaminizer.py
git commit -m "feat(agents): inject provider chain into CargoVitaminizerAgent"
```

---

## Task 5: Inject chain into SubjectsScoutAgent

**Files:**
- Modify: `backend/app/services/subjects_scout.py`
- Modify: `backend/tests/services/test_subjects_scout.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/services/test_subjects_scout.py`:

```python
# ── chain injection ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_extract_for_cargo_falls_back_to_second_provider():
    from app.services.subjects_scout import SubjectsScoutAgent
    from app.providers.base_provider import BaseLLMProvider
    from app.schemas.edital_schema import Cargo, Materia

    agent = SubjectsScoutAgent()

    failing = MagicMock(spec=BaseLLMProvider)
    failing.generate_json = AsyncMock(side_effect=Exception("quota"))

    from app.services.subjects_scout import CargoSubjects
    working = MagicMock(spec=BaseLLMProvider)
    working.generate_json = AsyncMock(return_value=CargoSubjects(
        titulo_cargo="Analista",
        materias=[Materia(nome="Português", topicos=["Gramática"])]
    ))

    chain = [failing, working]
    cargo = Cargo(titulo="Analista")
    result = await agent._extract_for_cargo(cargo, "texto do edital", chain)

    assert len(result) == 1
    assert result[0].nome == "Português"
    failing.generate_json.assert_awaited_once()
    working.generate_json.assert_awaited_once()


@pytest.mark.asyncio
async def test_extract_for_cargo_returns_empty_when_all_fail():
    from app.services.subjects_scout import SubjectsScoutAgent
    from app.providers.base_provider import BaseLLMProvider
    from app.schemas.edital_schema import Cargo

    agent = SubjectsScoutAgent()
    bad = MagicMock(spec=BaseLLMProvider)
    bad.generate_json = AsyncMock(side_effect=Exception("fail"))

    cargo = Cargo(titulo="Analista")
    result = await agent._extract_for_cargo(cargo, "texto", [bad])
    assert result == []
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /mnt/c/Dev/EstudoHub_4.0/backend
python -m pytest tests/services/test_subjects_scout.py::test_extract_for_cargo_falls_back_to_second_provider -v 2>&1 | tail -10
```

Expected: FAILED — `_extract_for_cargo` missing `chain` argument.

- [ ] **Step 3: Rewrite subjects_scout.py**

Replace the full contents of `backend/app/services/subjects_scout.py`:

```python
import re
import logging
import asyncio
from pathlib import Path
from typing import List

from pydantic import BaseModel

from app.providers.base_provider import BaseLLMProvider
from app.schemas.edital_schema import Cargo, Materia
from app.core.logging_streamer import log_streamer

logger = logging.getLogger(__name__)


class CargoSubjects(BaseModel):
    titulo_cargo: str
    materias: List[Materia]


class SubjectsScoutAgent:
    def __init__(self):
        self.semaphore = asyncio.Semaphore(2)

    async def scout(self, content_hash: str, cargos: List[Cargo], chain: List[BaseLLMProvider]) -> List[Cargo]:
        """Localiza e extrai o conteúdo programático para cada cargo."""
        storage_path = Path("backend/storage/processed") / content_hash
        if not storage_path.exists():
            storage_path = Path("storage/processed") / content_hash

        if not storage_path.exists():
            logger.error("Storage não encontrado para %s", content_hash)
            return cargos

        main_md = (storage_path / "main.md").read_text(encoding="utf-8") if (storage_path / "main.md").exists() else ""

        log_streamer.broadcast({"type": "log", "message": "🔍 Iniciando Subjects Scout (Minerador de Conteúdo)...", "level": "INFO"})

        content_section = self._find_subjects_section(main_md)
        if not content_section:
            log_streamer.broadcast({"type": "log", "message": "⚠️ Seção de Conteúdo Programático não detectada via heurística.", "level": "WARNING"})
            content_section = main_md[:30000]

        updated_cargos = []
        results = await asyncio.gather(*[self._extract_for_cargo(cargo, content_section, chain) for cargo in cargos])

        for cargo, materias in zip(cargos, results):
            cargo.materias = materias
            updated_cargos.append(cargo)
            if materias:
                log_streamer.broadcast({
                    "type": "log",
                    "message": f"📚 Matérias extraídas para {cargo.titulo}: {len(materias)} disciplinas encontradas.",
                    "level": "INFO"
                })

        return updated_cargos

    def _find_subjects_section(self, text: str) -> str:
        patterns = [
            r"CONTEÚDO PROGRAMÁTICO.*",
            r"DOS CONTEÚDOS PROGRAMÁTICOS.*",
            r"ANEXO [I|V|X]+.*CONTEÚDO.*",
            r"PROVAS OBJETIVAS.*CONHECIMENTOS.*"
        ]
        for p in patterns:
            match = re.search(p, text, re.IGNORECASE | re.DOTALL)
            if match:
                start = match.start()
                return text[start:start + 60000]
        return ""

    async def _extract_for_cargo(self, cargo: Cargo, section: str, chain: List[BaseLLMProvider]) -> List[Materia]:
        """Usa a chain de providers para extrair matérias e tópicos de um cargo."""
        async with self.semaphore:
            prompt = f"""
            Analise o fragmento do edital e extraia o CONTEÚDO PROGRAMÁTICO (Matérias e Tópicos) para o cargo: "{cargo.titulo}".

            REGRAS:
            1. Identifique as matérias (ex: Português, Raciocínio Lógico, Conhecimentos Específicos).
            2. Para cada matéria, liste os tópicos de estudo.
            3. Se o edital dividir em "Conhecimentos Básicos" e "Conhecimentos Específicos", extraia ambos.
            4. Ignore pesos e critérios de avaliação, foque apenas nos Tópicos.
            5. Retorne um JSON seguindo o schema CargoSubjects.

            TEXTO:
            {section}
            """

            for provider in chain:
                try:
                    result = await provider.generate_json(prompt=prompt, schema=CargoSubjects)
                    return result.materias
                except Exception as e:
                    logger.warning("⚠️ %s falhou, tentando próximo: %s", provider.__class__.__name__, e)
                    continue

            logger.error("Todos os providers falharam para cargo '%s'.", cargo.titulo)
            return []
```

- [ ] **Step 4: Run all subjects_scout tests**

```bash
cd /mnt/c/Dev/EstudoHub_4.0/backend
python -m pytest tests/services/test_subjects_scout.py -v 2>&1 | tail -25
```

Expected: all PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/subjects_scout.py backend/tests/services/test_subjects_scout.py
git commit -m "feat(agents): inject provider chain into SubjectsScoutAgent"
```

---

## Task 6: Slim down endpoints.py

**Files:**
- Modify: `backend/app/api/endpoints.py`

- [ ] **Step 1: Rewrite endpoints.py**

Replace the full contents of `backend/app/api/endpoints.py`:

```python
import asyncio
import json
import os
import logging
import hashlib
import uuid
from datetime import datetime
from typing import AsyncGenerator

import aiofiles
from fastapi import APIRouter, Request, UploadFile, File, HTTPException, BackgroundTasks
from sse_starlette.sse import EventSourceResponse

from app.core.logging_streamer import log_streamer
from app.schemas.edital_schema import IngestionResponse, StatusEdital
from app.services.pdf_service import PDFService
from app.services.subtractive_service import SubtractiveAgent, StorageResult
from app.services.ai_service import AIService

router = APIRouter()
subtractive_agent = SubtractiveAgent()
ai_service = AIService()
logger = logging.getLogger(__name__)

_SSE_KEEPALIVE_SECONDS = 15


def _compute_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def _broadcast_log(content_hash: str, message: str) -> None:
    logger.info(message)
    log_streamer.broadcast({"type": "log", "content_hash": content_hash, "message": message})


def _broadcast_error(content_hash: str, stage: str, error: Exception) -> None:
    message = f"[{stage}] {error}"
    logger.error("Erro no processamento (%s): %s", stage, error, exc_info=True)
    log_streamer.broadcast({
        "type": "error",
        "stage": stage,
        "content_hash": content_hash,
        "message": message,
    })


async def _process_edital_task(content_hash: str, temp_path: str):
    """Tarefa de segundo plano: extração → subtrativo → AI pipeline."""
    try:
        _broadcast_log(content_hash, f"Iniciando processamento para {content_hash}")

        # 1. Converter para Markdown
        _broadcast_log(content_hash, "Extraindo texto do PDF…")
        try:
            md_content = PDFService.to_markdown(temp_path)
        except Exception as e:
            _broadcast_error(content_hash, "pdf_extraction", e)
            return

        if not md_content.strip():
            _broadcast_error(content_hash, "pdf_extraction", ValueError("Conteúdo do PDF está vazio ou ilegível."))
            return

        _broadcast_log(content_hash, f"PDF extraído: {len(md_content)} caracteres")

        # 2. Processamento Subtrativo
        _broadcast_log(content_hash, "Iniciando processamento subtrativo…")
        enxuto_md, fragments = subtractive_agent.process(md_content)

        # 3. Persistência em Disco
        result_data = StorageResult(
            content_hash=content_hash,
            stripped_md=enxuto_md,
            tables={k: v for k, v in fragments.items() if k.startswith("FRAGMENT_TABLE_")},
            patterns={k: v for k, v in fragments.items() if not k.startswith("FRAGMENT_TABLE_")}
        )
        storage_path = subtractive_agent.persist(result_data)
        _broadcast_log(content_hash, f"Edital persistido em: {storage_path}")

        # 4 – 6. AI Pipeline (CargoTitle → Vitaminizer → SubjectsScout)
        _broadcast_log(content_hash, "Iniciando pipeline de IA…")
        result = await ai_service.process_edital(content_hash, enxuto_md)

        # 7. Notificar via SSE
        log_streamer.broadcast({
            "type": "data",
            "status": StatusEdital.PROCESSADO,
            "content_hash": content_hash,
            "edital": result["edital"].model_dump() if hasattr(result["edital"], "model_dump") else result["edital"],
            "cargos": [c.model_dump() if hasattr(c, "model_dump") else c for c in result["cargos"]],
        })
        _broadcast_log(content_hash, f"Processamento completo para {content_hash}")

    except Exception as e:
        _broadcast_error(content_hash, "processing", e)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as cleanup_err:
                logger.warning("Não foi possível remover arquivo temporário %s: %s", temp_path, cleanup_err)


@router.post("/upload", response_model=IngestionResponse)
async def upload_edital(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Recebe o arquivo e inicia o processamento em segundo plano."""
    file_bytes = await file.read()
    content_hash = _compute_hash(file_bytes)

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


@router.get("/cockpit/stream")
async def cockpit_stream(request: Request) -> EventSourceResponse:
    """SSE: transmite logs e eventos de dados em tempo real."""
    async def _event_generator() -> AsyncGenerator[dict, None]:
        queue = log_streamer.subscribe()
        logger.info("Cockpit SSE: novo cliente conectado.")
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=_SSE_KEEPALIVE_SECONDS)
                    yield {"event": message.get("type", "log"), "data": json.dumps(message, ensure_ascii=False)}
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": json.dumps({"type": "ping"})}
        finally:
            log_streamer.unsubscribe(queue)
            logger.info("Cockpit SSE: cliente desconectado.")

    return EventSourceResponse(_event_generator())
```

- [ ] **Step 2: Verify backend starts clean**

```bash
docker compose up -d --build backend 2>&1 | tail -5
sleep 5
curl -s http://localhost:8000/health
```

Expected: `{"status":"healthy","service":"backend"}`.

- [ ] **Step 3: Run full test suite**

```bash
cd /mnt/c/Dev/EstudoHub_4.0/backend
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: all PASSED (or pre-existing failures unrelated to this change).

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/endpoints.py
git commit -m "refactor(endpoints): delegate AI pipeline to AIService.process_edital"
```

---

## Task 7: Integration smoke test

**Files:** none — verification only.

- [ ] **Step 1: Rebuild and bring up all services**

```bash
docker compose up -d --build
```

- [ ] **Step 2: Confirm Ollama model is available**

```bash
docker exec estudohub_40-ollama-1 ollama list
```

If `llama3.1:8b` is not listed:

```bash
docker exec estudohub_40-ollama-1 ollama pull llama3.1:8b
```

- [ ] **Step 3: Confirm healthcheck**

```bash
curl -s http://localhost:8000/health
```

Expected: `{"status":"healthy","service":"backend"}`.

- [ ] **Step 4: Upload a sample edital and watch the chain in logs**

```bash
curl -s -X POST http://localhost:8000/api/v1/upload \
  -F "file=@/mnt/c/Dev/EstudoHub_4.0/sample_editais/cesgranrio/bb0122_edital.pdf" \
  | python3 -m json.tool
```

Then tail logs:

```bash
docker logs estudohub_40-backend-1 --follow 2>&1 | grep -E "chain|OllamaProvider|GroqProvider|NVIDIAProvider|OpenRouterProvider|GeminiProvider|falhou|tentando|process_edital|completo"
```

Expected log sequence:
```
AIService initialized — chain: OllamaProvider → GeminiProvider
process_edital [1931b0c]: chain=[OllamaProvider, GeminiProvider]
⚠️ OllamaProvider falhou, tentando próximo: ...   (if Ollama model not loaded)
GeminiProvider respondeu com sucesso.              (or Ollama if model is ready)
Processamento completo para 1931b0c...
```

- [ ] **Step 5: Final commit**

```bash
git add .
git commit -m "feat: complete AI provider chain refactor — Ollama-first with C1 injection"
```
