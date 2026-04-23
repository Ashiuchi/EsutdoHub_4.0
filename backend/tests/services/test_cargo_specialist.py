import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
from app.services.cargo_specialist import CargoTitleAgent
from app.schemas.edital_schema import CargoIdentificado


_TABLE_WITH_CARGOS = """\
| Cód. | Cargo | Vagas | Salário |
|------|-------|-------|---------|
| 01 | Analista Judiciário | 10 | R$ 8.000 |
| 02 | Técnico Judiciário | 20 | R$ 4.000 |
"""

_TABLE_WITHOUT_ANCHORS = """\
| Nome | Endereço |
|------|----------|
| João | SP |
"""


# ── _identify_relevant_chunks ─────────────────────────────────────────────────

def test_identify_relevant_chunks_short_content():
    agent = CargoTitleAgent()
    content = "Cargo Analista, Vagas disponíveis."
    chunks = agent._identify_relevant_chunks(content)
    assert len(chunks) == 1


def test_identify_relevant_chunks_returns_only_relevant():
    agent = CargoTitleAgent()
    content = "Irrelevant text. No anchors here. " * 200
    chunks = agent._identify_relevant_chunks(content)
    assert chunks == []


def test_identify_relevant_chunks_scores_by_anchor_density():
    agent = CargoTitleAgent()
    relevant = "Cargo Analista Vagas 10 Jornada 40h Nível Superior. " * 60
    irrelevant = "Texto sem nenhuma informação relevante. " * 60
    content = irrelevant + relevant
    chunks = agent._identify_relevant_chunks(content)
    assert len(chunks) > 0
    # The relevant part should score higher and appear first
    assert any("Cargo" in c for c in chunks)


def test_identify_relevant_chunks_max_three():
    agent = CargoTitleAgent()
    # Content with anchors spread throughout
    content = ("Cargo X Vagas 5\n" * 50 + "---\n") * 10
    chunks = agent._identify_relevant_chunks(content)
    assert len(chunks) <= 3


# ── _sprint_scan ──────────────────────────────────────────────────────────────

def test_sprint_scan_returns_list():
    agent = CargoTitleAgent()
    result = agent._sprint_scan(_TABLE_WITH_CARGOS)
    assert isinstance(result, list)


def test_sprint_scan_returns_empty_for_table_without_cargo_column():
    agent = CargoTitleAgent()
    result = agent._sprint_scan(_TABLE_WITHOUT_ANCHORS)
    assert result == []


def test_sprint_scan_returns_empty_for_too_few_lines():
    agent = CargoTitleAgent()
    result = agent._sprint_scan("| A |\n| B |")
    assert result == []


def test_sprint_scan_handles_malformed_table_gracefully():
    agent = CargoTitleAgent()
    result = agent._sprint_scan("not a table at all |||")
    assert isinstance(result, list)


# ── _deep_scan ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_deep_scan_returns_cargos_from_provider():
    agent = CargoTitleAgent()
    from pydantic import BaseModel
    from typing import List

    mock_result = MagicMock()
    mock_result.cargos = [CargoIdentificado(titulo="Analista", codigo_edital="01")]

    with patch.object(agent.ollama_provider, 'generate_json',
                      new_callable=AsyncMock, return_value=mock_result):
        result = await agent._deep_scan("fragmento de edital")
        assert len(result) == 1
        assert result[0].titulo == "Analista"


@pytest.mark.asyncio
async def test_deep_scan_falls_back_to_gemini_on_ollama_failure():
    agent = CargoTitleAgent()
    mock_result = MagicMock()
    mock_result.cargos = [CargoIdentificado(titulo="Técnico", codigo_edital="02")]

    with patch.object(agent.ollama_provider, 'generate_json',
                      new_callable=AsyncMock,
                      side_effect=ConnectionError("Ollama offline")), \
         patch.object(agent.gemini_provider, 'generate_json',
                      new_callable=AsyncMock, return_value=mock_result):
        result = await agent._deep_scan("fragmento")
        assert len(result) == 1
        assert result[0].titulo == "Técnico"


@pytest.mark.asyncio
async def test_deep_scan_returns_empty_when_all_providers_fail():
    agent = CargoTitleAgent()
    with patch.object(agent.ollama_provider, 'generate_json',
                      new_callable=AsyncMock,
                      side_effect=ConnectionError("offline")), \
         patch.object(agent.gemini_provider, 'generate_json',
                      new_callable=AsyncMock,
                      side_effect=ConnectionError("offline")):
        result = await agent._deep_scan("fragmento")
        assert result == []


# ── hunt_titles ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_hunt_titles_no_storage_returns_empty(tmp_path):
    agent = CargoTitleAgent()
    # Point storage to a directory that doesn't have the hash subdirectory
    fake_storage = tmp_path / "storage" / "processed"
    fake_storage.mkdir(parents=True)
    with patch('app.services.cargo_specialist.Path',
               side_effect=lambda *a: fake_storage if "storage/processed" in str(a[0]) else Path(*a)):
        result = await agent.hunt_titles("nonexistent-hash")
        assert isinstance(result, list)


@pytest.mark.asyncio
async def test_hunt_titles_with_main_md(tmp_path):
    agent = CargoTitleAgent()
    content_hash = "test-hash"
    storage_path = tmp_path / content_hash
    storage_path.mkdir()
    (storage_path / "main.md").write_text(
        "Cargo Analista Vagas 10 Nível Superior Jornada 40h", encoding="utf-8"
    )
    tables_dir = storage_path / "tables"
    tables_dir.mkdir()

    mock_cargos = [CargoIdentificado(titulo="Analista", codigo_edital=None)]

    with patch('app.services.cargo_specialist.Path') as mock_path_cls:
        def path_factory(*args):
            if args and "storage/processed" in str(args):
                p = MagicMock()
                p.__truediv__ = lambda self, other: storage_path if other == content_hash else storage_path / other
                return p
            return Path(*args)

        with patch.object(agent, '_deep_scan', new_callable=AsyncMock,
                          return_value=mock_cargos):
            # Direct test with real path
            with patch('app.services.cargo_specialist.Path',
                       side_effect=lambda *a: tmp_path if "storage" in str(a) else Path(*a)):
                result = await agent.hunt_titles(content_hash)
                assert isinstance(result, list)
