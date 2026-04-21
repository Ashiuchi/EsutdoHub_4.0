# Subtractive Processing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove known structures (tables, monetary values, dates) from raw Markdown before LLM extraction, producing a lean "Markdown Enxuto" processed in chunks and table fragments processed individually for higher accuracy.

**Architecture:** A new `SubtractiveAgent` applies two sequential regex passes (tables → patterns), replacing matches with `[[FRAGMENT_*]]` markers and storing originals in a fragments dict. `AIService` consumes this output by processing table fragments one-by-one via LLM (small context → high accuracy) and then chunking the stripped Markdown normally, merging all `Cargo` results at the end.

**Tech Stack:** `re` (stdlib), `json` (stdlib), existing `BaseLLMProvider` chain, Pydantic, pytest + pytest-asyncio. **No pandas** — table blocks are extracted as raw strings and sent directly to the LLM; pandas would add a heavy dependency with no benefit here.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| **Create** | `backend/app/services/subtractive_service.py` | `SubtractiveAgent`: regex strip of tables and patterns |
| **Create** | `backend/app/schemas/edital_schema.py` (add class) | `TabelaExtraida`: Pydantic schema for table-only LLM extractions |
| **Create** | `backend/tests/services/test_subtractive_service.py` | Unit tests for `SubtractiveAgent` |
| **Modify** | `backend/app/services/ai_service.py` | Integrate agent, add `_extract_cargos_from_table`, update orchestration |
| **Modify** | `backend/tests/services/test_ai_service_orchestration.py` | Fix RuntimeError message assertions, add table-extraction tests |

---

## Task 1: SubtractiveAgent — `strip_tables`

**Files:**
- Create: `backend/app/services/subtractive_service.py`
- Create: `backend/tests/services/test_subtractive_service.py`

- [ ] **Step 1.1: Write the failing test**

```python
# backend/tests/services/test_subtractive_service.py
import pytest
from app.services.subtractive_service import SubtractiveAgent

SAMPLE_TABLE = """\
Antes da tabela.

| Cargo | Vagas | Salário |
|-------|-------|---------|
| Analista | 10 | R$ 5.000 |
| Técnico | 20 | R$ 3.000 |

Depois da tabela.
"""

def test_strip_tables_removes_table_block():
    agent = SubtractiveAgent()
    stripped, fragments = agent.strip_tables(SAMPLE_TABLE)

    assert "| Cargo |" not in stripped
    assert "|-------|" not in stripped
    assert "Antes da tabela." in stripped
    assert "Depois da tabela." in stripped


def test_strip_tables_creates_marker():
    agent = SubtractiveAgent()
    stripped, fragments = agent.strip_tables(SAMPLE_TABLE)

    assert "[[FRAGMENT_TABLE_0]]" in stripped


def test_strip_tables_stores_fragment():
    agent = SubtractiveAgent()
    _, fragments = agent.strip_tables(SAMPLE_TABLE)

    assert "FRAGMENT_TABLE_0" in fragments
    assert "| Cargo |" in fragments["FRAGMENT_TABLE_0"]


def test_strip_tables_multiple_tables():
    md = "| A |\n|---|\n| 1 |\n\nTexto\n\n| B |\n|---|\n| 2 |\n"
    agent = SubtractiveAgent()
    stripped, fragments = agent.strip_tables(md)

    assert "FRAGMENT_TABLE_0" in fragments
    assert "FRAGMENT_TABLE_1" in fragments
    assert "[[FRAGMENT_TABLE_0]]" in stripped
    assert "[[FRAGMENT_TABLE_1]]" in stripped


def test_strip_tables_no_tables_unchanged():
    md = "Texto simples sem tabelas.\nSegunda linha."
    agent = SubtractiveAgent()
    stripped, fragments = agent.strip_tables(md)

    assert stripped == md
    assert fragments == {}
```

- [ ] **Step 1.2: Run test to verify it fails**

```bash
cd backend && pytest tests/services/test_subtractive_service.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.services.subtractive_service'`

- [ ] **Step 1.3: Implement `SubtractiveAgent.strip_tables`**

```python
# backend/app/services/subtractive_service.py
import json
import logging
import re
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

# Matches one or more consecutive lines that start (after optional whitespace) with |
_TABLE_RE = re.compile(r'(?m)(?:^[ \t]*\|[^\n]*(?:\n|$))+')


class SubtractiveAgent:
    """Removes known structures from Markdown, replacing them with [[FRAGMENT_*]] markers."""

    def strip_tables(self, md: str) -> Tuple[str, Dict[str, str]]:
        """Remove markdown table blocks and replace with markers.

        Returns:
            (stripped_md, fragments) where fragments maps marker keys to original content.
        """
        fragments: Dict[str, str] = {}
        counter = 0

        def _replacer(match: re.Match) -> str:
            nonlocal counter
            key = f"FRAGMENT_TABLE_{counter}"
            fragments[key] = match.group(0)
            counter += 1
            return f"[[{key}]]"

        stripped = _TABLE_RE.sub(_replacer, md)
        logger.debug(f"strip_tables: removed {len(fragments)} table(s).")
        return stripped, fragments
```

- [ ] **Step 1.4: Run test to verify it passes**

```bash
cd backend && pytest tests/services/test_subtractive_service.py -v
```

Expected: all 5 tests PASS

- [ ] **Step 1.5: Commit**

```bash
git add backend/app/services/subtractive_service.py backend/tests/services/test_subtractive_service.py
git commit -m "feat(subtractive): add SubtractiveAgent.strip_tables with marker replacement"
```

---

## Task 2: SubtractiveAgent — `strip_patterns` and `process`

**Files:**
- Modify: `backend/app/services/subtractive_service.py`
- Modify: `backend/tests/services/test_subtractive_service.py`

- [ ] **Step 2.1: Write the failing tests**

Append to `backend/tests/services/test_subtractive_service.py`:

```python
SAMPLE_WITH_PATTERNS = """\
Salário de R$ 5.000,00 por mês.
Inscrições até 30/06/2025.
Valor da taxa: R$ 120,50.
Data da prova: 15/08/25.
"""

def test_strip_patterns_removes_money():
    agent = SubtractiveAgent()
    stripped, fragments = agent.strip_patterns(SAMPLE_WITH_PATTERNS)

    assert "R$" not in stripped
    money_keys = [k for k in fragments if k.startswith("FRAGMENT_MONEY_")]
    assert len(money_keys) == 2


def test_strip_patterns_removes_dates():
    agent = SubtractiveAgent()
    stripped, fragments = agent.strip_patterns(SAMPLE_WITH_PATTERNS)

    assert "30/06/2025" not in stripped
    assert "15/08/25" not in stripped
    date_keys = [k for k in fragments if k.startswith("FRAGMENT_DATE_")]
    assert len(date_keys) == 2


def test_strip_patterns_creates_markers():
    agent = SubtractiveAgent()
    stripped, fragments = agent.strip_patterns(SAMPLE_WITH_PATTERNS)

    assert "[[FRAGMENT_MONEY_0]]" in stripped
    assert "[[FRAGMENT_DATE_0]]" in stripped


def test_process_applies_both_passes():
    md = "| Cargo | Salário |\n|-------|----------|\n| Analista | R$ 5.000 |\n\nData: 01/01/2025."
    agent = SubtractiveAgent()
    stripped, fragments = agent.process(md)

    table_keys = [k for k in fragments if k.startswith("FRAGMENT_TABLE_")]
    money_keys = [k for k in fragments if k.startswith("FRAGMENT_MONEY_")]
    date_keys = [k for k in fragments if k.startswith("FRAGMENT_DATE_")]

    assert len(table_keys) == 1
    assert len(money_keys) == 0  # R$ inside table → captured in table fragment, not loose
    assert len(date_keys) == 1
    assert "[[FRAGMENT_TABLE_0]]" in stripped
    assert "[[FRAGMENT_DATE_0]]" in stripped


def test_process_reduces_content_size():
    md = "| A | B |\n|---|---|\n| 1 | 2 |\n\n" * 10 + "Texto final."
    agent = SubtractiveAgent()
    stripped, _ = agent.process(md)

    assert len(stripped) < len(md)
```

- [ ] **Step 2.2: Run tests to verify they fail**

```bash
cd backend && pytest tests/services/test_subtractive_service.py::test_strip_patterns_removes_money -v
```

Expected: `AttributeError: 'SubtractiveAgent' object has no attribute 'strip_patterns'`

- [ ] **Step 2.3: Implement `strip_patterns` and `process`**

Add to `backend/app/services/subtractive_service.py`, after the `_TABLE_RE` constant:

```python
_MONEY_RE = re.compile(r'R\$\s*[\d.,]+')
_DATE_RE = re.compile(r'\b\d{2}/\d{2}/(?:\d{4}|\d{2})\b')
```

Add these two methods inside `SubtractiveAgent` (after `strip_tables`):

```python
    def strip_patterns(self, md: str) -> Tuple[str, Dict[str, str]]:
        """Remove monetary values and dates, replacing with markers.

        Returns:
            (stripped_md, fragments)
        """
        fragments: Dict[str, str] = {}
        money_counter = 0
        date_counter = 0

        def _money_replacer(match: re.Match) -> str:
            nonlocal money_counter
            key = f"FRAGMENT_MONEY_{money_counter}"
            fragments[key] = match.group(0)
            money_counter += 1
            return f"[[{key}]]"

        def _date_replacer(match: re.Match) -> str:
            nonlocal date_counter
            key = f"FRAGMENT_DATE_{date_counter}"
            fragments[key] = match.group(0)
            date_counter += 1
            return f"[[{key}]]"

        stripped = _MONEY_RE.sub(_money_replacer, md)
        stripped = _DATE_RE.sub(_date_replacer, stripped)
        logger.debug(f"strip_patterns: removed {money_counter} monetary value(s), {date_counter} date(s).")
        return stripped, fragments

    def process(self, md: str) -> Tuple[str, Dict[str, str]]:
        """Full subtractive pass: tables first, then monetary values and dates.

        Tables are stripped first so their embedded R$ and dates are captured
        as part of the table fragment, not as loose pattern fragments.

        Returns:
            (markdown_enxuto, all_fragments)
        """
        stripped, table_fragments = self.strip_tables(md)
        stripped, pattern_fragments = self.strip_patterns(stripped)
        all_fragments = {**table_fragments, **pattern_fragments}

        reduction = len(md) - len(stripped)
        logger.info(
            f"SubtractiveAgent.process: {len(md)} → {len(stripped)} chars "
            f"(−{reduction}, {len(table_fragments)} tables, "
            f"{len(pattern_fragments)} patterns)"
        )
        return stripped, all_fragments
```

- [ ] **Step 2.4: Run all subtractive tests**

```bash
cd backend && pytest tests/services/test_subtractive_service.py -v
```

Expected: all 10 tests PASS

- [ ] **Step 2.5: Commit**

```bash
git add backend/app/services/subtractive_service.py backend/tests/services/test_subtractive_service.py
git commit -m "feat(subtractive): add strip_patterns and process method to SubtractiveAgent"
```

---

## Task 3: `TabelaExtraida` Pydantic Schema

**Files:**
- Modify: `backend/app/schemas/edital_schema.py`

This schema is used by `AIService._extract_cargos_from_table`. It is intentionally minimal — the LLM only needs to return `cargos` when given a table block, not full edital metadata.

- [ ] **Step 3.1: Add `TabelaExtraida` to `edital_schema.py`**

Open `backend/app/schemas/edital_schema.py` and append at the end of the file:

```python

class TabelaExtraida(BaseModel):
    """Schema restrito para extrações de blocos de tabela individuais.
    Não inclui metadados globais do edital (orgao, banca) para evitar alucinações.
    """
    cargos: List[Cargo] = []
```

- [ ] **Step 3.2: Verify syntax**

```bash
python3 -m py_compile backend/app/schemas/edital_schema.py && echo "OK"
```

Expected: `OK`

- [ ] **Step 3.3: Commit**

```bash
git add backend/app/schemas/edital_schema.py
git commit -m "feat(schema): add TabelaExtraida for isolated table LLM extraction"
```

---

## Task 4: `AIService._extract_cargos_from_table`

**Files:**
- Modify: `backend/app/services/ai_service.py`
- Modify: `backend/tests/services/test_ai_service_orchestration.py`

- [ ] **Step 4.1: Write the failing test**

Append to `backend/tests/services/test_ai_service_orchestration.py`:

```python
from app.schemas.edital_schema import TabelaExtraida


@pytest.mark.asyncio
async def test_extract_cargos_from_table_returns_cargo_list():
    """_extract_cargos_from_table must call provider with table content and return Cargo list."""
    service = AIService()

    mock_table_result = TabelaExtraida(
        cargos=[
            Cargo(
                titulo="Analista",
                vagas_ampla=10,
                vagas_cotas=2,
                salario=5000.0,
                requisitos="Superior completo",
                materias=[],
            )
        ]
    )

    with patch.object(service.ollama_provider, 'generate_json', new_callable=AsyncMock) as mock_ollama:
        mock_ollama.return_value = mock_table_result

        table_md = "| Cargo | Vagas |\n|-------|-------|\n| Analista | 10 |\n"
        result = await service._extract_cargos_from_table("FRAGMENT_TABLE_0", table_md)

        assert len(result) == 1
        assert result[0].titulo == "Analista"
        call_kwargs = mock_ollama.call_args
        assert "FRAGMENT_TABLE_0" in call_kwargs.kwargs["prompt"] or "FRAGMENT_TABLE_0" in call_kwargs.args[0]


@pytest.mark.asyncio
async def test_extract_cargos_from_table_returns_empty_on_provider_failure():
    """_extract_cargos_from_table must return [] when all providers fail (non-fatal)."""
    service = AIService()

    with patch.object(service.ollama_provider, 'generate_json', new_callable=AsyncMock) as mock_ollama, \
         patch.object(service.gemini_provider, 'generate_json', new_callable=AsyncMock) as mock_gemini:
        mock_ollama.side_effect = ConnectionError("down")
        mock_gemini.side_effect = ConnectionError("down")

        result = await service._extract_cargos_from_table("FRAGMENT_TABLE_0", "| A |\n|---|\n| 1 |\n")

        assert result == []
```

- [ ] **Step 4.2: Run tests to verify they fail**

```bash
cd backend && pytest tests/services/test_ai_service_orchestration.py::test_extract_cargos_from_table_returns_cargo_list -v
```

Expected: `AttributeError: 'AIService' object has no attribute '_extract_cargos_from_table'`

- [ ] **Step 4.3: Add imports and method to `ai_service.py`**

At the top of `backend/app/services/ai_service.py`, update the schema import line:

```python
from app.schemas.edital_schema import Cargo, EditalGeral, EditalResponse, Materia, StatusEdital, TabelaExtraida
```

Add this method to `AIService` (place it after `_extract_from_chunk`, before `_merge_materias`):

```python
    async def _extract_cargos_from_table(self, fragment_key: str, table_md: str) -> List[Cargo]:
        """Extract Cargo list from a single isolated table fragment via LLM.

        Uses TabelaExtraida schema (cargos only) to minimize hallucination risk.
        Returns empty list on provider failure so table errors are non-fatal.

        Args:
            fragment_key: Identifier for logging (e.g. "FRAGMENT_TABLE_0").
            table_md: Raw markdown of the table block.

        Returns:
            List of Cargo instances extracted from the table, or [] on failure.
        """
        prompt = (
            f"Analise o bloco de TABELA MARKDOWN abaixo ({fragment_key}) extraído de um edital de concurso público.\n"
            "Extraia apenas os dados de CARGOS presentes (titulo, vagas, salário, requisitos, matérias).\n"
            "Se a tabela não contiver dados de cargo, retorne {\"cargos\": []}.\n"
            f"Retorne APENAS o JSON puro seguindo este schema:\n{TabelaExtraida.model_json_schema()}\n\n"
            f"TABELA:\n{table_md}"
        )

        for provider in self._get_provider_chain():
            try:
                result: TabelaExtraida = await provider.generate_json(prompt=prompt, schema=TabelaExtraida)
                logger.info(f"{fragment_key}: {len(result.cargos)} cargo(s) extraído(s) via {provider.__class__.__name__}.")
                return result.cargos
            except (ConnectionError, TimeoutError, ValueError) as e:
                logger.warning(f"{fragment_key}: {provider.__class__.__name__} falhou — {e}")
                continue
            except Exception as e:
                logger.error(f"{fragment_key}: erro inesperado — {e}")

        logger.warning(f"{fragment_key}: todos os providers falharam. Fragmento ignorado.")
        return []
```

- [ ] **Step 4.4: Run tests to verify they pass**

```bash
cd backend && pytest tests/services/test_ai_service_orchestration.py::test_extract_cargos_from_table_returns_cargo_list tests/services/test_ai_service_orchestration.py::test_extract_cargos_from_table_returns_empty_on_provider_failure -v
```

Expected: both PASS

- [ ] **Step 4.5: Commit**

```bash
git add backend/app/services/ai_service.py backend/tests/services/test_ai_service_orchestration.py
git commit -m "feat(ai): add _extract_cargos_from_table for isolated table fragment LLM extraction"
```

---

## Task 5: Integrate SubtractiveAgent into `extract_edital_data`

**Files:**
- Modify: `backend/app/services/ai_service.py`
- Modify: `backend/tests/services/test_ai_service_orchestration.py`

This is the core integration task. The new flow is:

```
md_content
  → SubtractiveAgent.process()
      → stripped_md + fragments (tables + patterns)
  → For each FRAGMENT_TABLE_*:
      → _extract_cargos_from_table()  ← small context, high accuracy
  → stripped_md → chunker → _extract_from_chunk() per chunk  ← same as before
  → merge(table_cargos + chunk_cargos)
  → _create_edital_db() + _persist_cargos_sync()
  → EditalResponse
```

- [ ] **Step 5.1: Fix existing failing tests (RuntimeError message mismatch)**

In `backend/tests/services/test_ai_service_orchestration.py`, find and replace the two `match=` assertions:

```python
# BEFORE (two occurrences):
with pytest.raises(RuntimeError, match="All LLM providers failed"):

# AFTER (both occurrences):
with pytest.raises(RuntimeError, match="Todos os providers LLM falharam"):
```

Run to confirm they now pass:
```bash
cd backend && pytest tests/services/test_ai_service_orchestration.py -v
```

Expected: all existing tests PASS (the two previously failing ones now pass too)

- [ ] **Step 5.2: Add integration test for SubtractiveAgent in orchestration**

Append to `backend/tests/services/test_ai_service_orchestration.py`:

```python
from unittest.mock import patch as _patch
from app.schemas.edital_schema import TabelaExtraida


@pytest.mark.asyncio
async def test_extract_edital_data_processes_table_fragments():
    """SubtractiveAgent is invoked; table fragments are sent to _extract_cargos_from_table."""
    service = AIService()

    md_with_table = (
        "Órgão: Test Org\nBanca: Test Bank\n\n"
        "| Cargo | Vagas |\n|-------|-------|\n| Analista | 10 |\n\n"
        "Informações adicionais."
    )

    mock_edital = EditalGeral(
        orgao="Test Org",
        banca="Test Bank",
        data_prova=None,
        periodo_inscricao=None,
        link_edital=None,
        cargos=[],
    )
    mock_table_result = TabelaExtraida(
        cargos=[
            Cargo(
                titulo="Analista",
                vagas_ampla=10,
                vagas_cotas=2,
                salario=5000.0,
                requisitos="Superior completo",
                materias=[],
            )
        ]
    )

    with patch.object(service.ollama_provider, 'generate_json', new_callable=AsyncMock) as mock_ollama:
        # First call: table extraction → TabelaExtraida
        # Second call: stripped md extraction → EditalGeral
        mock_ollama.side_effect = [mock_table_result, mock_edital]

        with patch('app.services.ai_service.AIService._create_edital_sync', return_value=None):
            result = await service.extract_edital_data(md_content=md_with_table)

        assert result.orgao == "Test Org"
        # Table was processed: Analista should appear in merged cargos
        cargo_titulos = [c.titulo for c in result.cargos]
        assert "Analista" in cargo_titulos
        assert mock_ollama.call_count == 2
```

- [ ] **Step 5.3: Run the new test to verify it fails**

```bash
cd backend && pytest tests/services/test_ai_service_orchestration.py::test_extract_edital_data_processes_table_fragments -v
```

Expected: FAIL (table fragment not yet integrated into `extract_edital_data`)

- [ ] **Step 5.4: Update `extract_edital_data` in `ai_service.py`**

Add this import at the top (next to existing imports):

```python
from app.services.subtractive_service import SubtractiveAgent
```

Replace the entire `extract_edital_data` method body with:

```python
    async def extract_edital_data(self, md_content: str) -> EditalResponse:
        """Extrai dados estruturados de um edital usando processamento subtrativo.

        Fluxo:
        1. SubtractiveAgent remove tabelas e padrões, gerando markdown_enxuto + fragmentos.
        2. Cada fragmento de tabela é processado individualmente via LLM (contexto pequeno).
        3. O markdown_enxuto é processado em single-pass ou chunks (conforme tamanho).
        4. Todos os cargos são consolidados e persistidos.

        Args:
            md_content: Conteúdo do edital convertido para markdown.

        Returns:
            EditalResponse com metadados, cargos consolidados, id e status do banco.

        Raises:
            RuntimeError: Se nenhum cargo nem metadados forem extraídos.
        """
        # ── Phase 1: Subtractive pass ─────────────────────────────────────
        agent = SubtractiveAgent()
        stripped_md, fragments = agent.process(md_content)

        # ── Phase 2: Extract from table fragments (parallel-friendly, small context) ──
        table_cargos: List[Cargo] = []
        for key, table_content in fragments.items():
            if not key.startswith("FRAGMENT_TABLE_"):
                continue
            log_streamer.broadcast({
                "type": "log",
                "message": f"📊 Processando fragmento de tabela: {key}",
                "level": "INFO",
            })
            extracted = await self._extract_cargos_from_table(key, table_content)
            table_cargos.extend(extracted)

        logger.info(f"Fragmentos de tabela: {len(table_cargos)} cargo(s) extraído(s).")

        # ── Phase 3: Process stripped markdown ────────────────────────────
        # Prompt hint: tell the LLM that [[FRAGMENT_*]] markers are already processed
        marker_hint = (
            "\nNOTA: Os marcadores [[FRAGMENT_TABLE_N]], [[FRAGMENT_MONEY_N]] e "
            "[[FRAGMENT_DATE_N]] indicam dados já extraídos separadamente. Ignore-os."
        )
        stripped_md_with_hint = stripped_md + marker_hint

        if len(stripped_md_with_hint) <= CHUNK_THRESHOLD:
            logger.info(f"Markdown enxuto ({len(stripped_md_with_hint)} chars) — single-pass.")
            result = await self._extract_from_chunk(stripped_md_with_hint)
            if result is None:
                raise RuntimeError("Todos os providers LLM falharam na extração.")

            # Merge table cargos into result
            merged_cargos = self._merge_cargos(table_cargos, result.cargos)
            result = result.model_copy(update={"cargos": merged_cargos})

            edital_db_id = await self._create_edital_db(result)
            if edital_db_id:
                await self._persist_and_broadcast(edital_db_id, result.cargos, set())

            return EditalResponse(
                **result.model_dump(),
                id=edital_db_id,
                status=StatusEdital.INGESTADO,
            )

        # ── Chunked path ──────────────────────────────────────────────────
        chunker = MarkdownChunker(chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
        chunks = chunker.split(stripped_md_with_hint)
        total = len(chunks)
        logger.info(f"Markdown enxuto grande ({len(stripped_md_with_hint)} chars) → {total} chunks.")

        merged: Optional[EditalGeral] = None
        edital_db_id: Optional[int] = None
        known_titulos: Set[str] = set()
        failed_chunks: List[int] = []

        for idx, chunk in enumerate(chunks, start=1):
            logger.info(f"Processando chunk {idx}/{total} ({len(chunk)} chars)...")
            result = await self._extract_from_chunk(chunk)
            await asyncio.sleep(2.0)

            if result is None:
                logger.warning(f"Chunk {idx}/{total} falhou — pulando.")
                failed_chunks.append(idx)
                continue

            if merged is None:
                merged = result
                logger.info(f"Chunk {idx}: metadados capturados, {len(result.cargos)} cargo(s).")
                edital_db_id = await self._create_edital_db(result)
                if edital_db_id:
                    await self._persist_and_broadcast(edital_db_id, result.cargos, known_titulos)
            else:
                new_cargos = [c for c in result.cargos if c.titulo not in known_titulos]
                if edital_db_id and new_cargos:
                    await self._persist_and_broadcast(edital_db_id, new_cargos, known_titulos)
                merged_cargos = self._merge_cargos(merged.cargos, result.cargos)
                merged = merged.model_copy(update={"cargos": merged_cargos})
                logger.info(f"Chunk {idx}/{total}: total consolidado={len(merged.cargos)} cargo(s).")

        if merged is None or not merged.cargos:
            raise RuntimeError(
                f"Todos os providers LLM falharam na extração. "
                f"Chunks falhos: {failed_chunks}/{total}"
            )

        # Merge table cargos into final chunked result
        final_cargos = self._merge_cargos(table_cargos, merged.cargos)
        merged = merged.model_copy(update={"cargos": final_cargos})

        if failed_chunks:
            logger.warning(f"Extração concluída com {len(failed_chunks)} chunk(s) falho(s): {failed_chunks}")

        logger.info(f"EditalGeral consolidado — {len(merged.cargos)} cargo(s) no total.")
        return EditalResponse(
            **merged.model_dump(),
            id=edital_db_id,
            status=StatusEdital.INGESTADO,
        )
```

- [ ] **Step 5.5: Run all orchestration tests**

```bash
cd backend && pytest tests/services/test_ai_service_orchestration.py -v
```

Expected: all tests PASS

- [ ] **Step 5.6: Run full test suite**

```bash
cd backend && pytest -v
```

Expected: all tests PASS (or pre-existing failures unrelated to this feature)

- [ ] **Step 5.7: Commit**

```bash
git add backend/app/services/ai_service.py backend/tests/services/test_ai_service_orchestration.py
git commit -m "feat(ai): integrate SubtractiveAgent into extract_edital_data orchestration"
```

---

## Task 6: Debug Persistence (`stripped_edital.md` and `fragments.json`)

**Files:**
- Modify: `backend/app/services/ai_service.py`

The debug files must be saved **after** the subtractive pass and **before** any LLM calls, so even if extraction fails we have the debug artefacts.

- [ ] **Step 6.1: Add static debug helpers to `AIService`**

Add these two static methods to `AIService`, just before `extract_edital_data`:

```python
    @staticmethod
    def _save_debug_stripped(stripped_md: str) -> None:
        """Salva o markdown enxuto (após remoção subtrativa) em debug/stripped_edital.md."""
        import os
        try:
            os.makedirs("debug", exist_ok=True)
            with open("debug/stripped_edital.md", "w", encoding="utf-8") as f:
                f.write(stripped_md)
            logger.info("Debug: stripped_edital.md salvo.")
        except Exception as e:
            logger.error(f"Falha ao salvar stripped_edital.md: {e}")

    @staticmethod
    def _save_debug_fragments(fragments: Dict[str, str]) -> None:
        """Salva os fragmentos extraídos (tabelas e padrões) em debug/fragments.json."""
        import json
        import os
        try:
            os.makedirs("debug", exist_ok=True)
            with open("debug/fragments.json", "w", encoding="utf-8") as f:
                json.dump(fragments, f, ensure_ascii=False, indent=2)
            logger.info(f"Debug: fragments.json salvo ({len(fragments)} fragmento(s)).")
        except Exception as e:
            logger.error(f"Falha ao salvar fragments.json: {e}")
```

You also need to add `Dict` to the typing import at the top of the file:

```python
from typing import Dict, List, Optional, Set
```

- [ ] **Step 6.2: Call debug helpers in `extract_edital_data`**

In `extract_edital_data`, immediately after `stripped_md, fragments = agent.process(md_content)`, add:

```python
        self._save_debug_stripped(stripped_md)
        self._save_debug_fragments(fragments)
```

The relevant section should look like:

```python
        # ── Phase 1: Subtractive pass ─────────────────────────────────────
        agent = SubtractiveAgent()
        stripped_md, fragments = agent.process(md_content)
        self._save_debug_stripped(stripped_md)
        self._save_debug_fragments(fragments)
```

- [ ] **Step 6.3: Run full test suite to confirm nothing broke**

```bash
cd backend && pytest -v
```

Expected: all tests PASS

- [ ] **Step 6.4: Commit**

```bash
git add backend/app/services/ai_service.py
git commit -m "feat(debug): persist stripped_edital.md and fragments.json after subtractive pass"
```

---

## Self-Review

### Spec Coverage

| Requirement | Task | Status |
|---|---|---|
| `SubtractiveAgent` class | Task 1–2 | ✅ |
| `strip_tables` with `[[FRAGMENT_TABLE_N]]` markers | Task 1 | ✅ |
| `strip_patterns` for `R$ ...` and dates | Task 2 | ✅ |
| Fragments dict returned | Task 1–2 | ✅ |
| Process table fragments via IA individually | Task 4–5 | ✅ |
| Process markdown_enxuto in chunks | Task 5 | ✅ |
| Consolidate all results | Task 5 | ✅ |
| `debug/stripped_edital.md` | Task 6 | ✅ |
| `debug/fragments.json` | Task 6 | ✅ |
| Prompt tells LLM about `[[FRAGMENT_*]]` markers | Task 5 (`marker_hint`) | ✅ |
| pandas "if necessary" | N/A | ✅ (not needed, avoided heavy dep) |

### Placeholder Scan

No TBD, TODO, or vague steps found. All code blocks are complete.

### Type Consistency

- `SubtractiveAgent.process()` → `Tuple[str, Dict[str, str]]` — consistent across Tasks 1, 2, 5, 6.
- `_extract_cargos_from_table()` → `List[Cargo]` — consistent across Tasks 4 and 5.
- `TabelaExtraida.cargos: List[Cargo]` — used in Task 4 mock and Task 5 test.
- `Dict` added to typing imports in Task 6 — required by helper type hints.
- `extract_edital_data` → `EditalResponse` — unchanged from prior session; consistent.
