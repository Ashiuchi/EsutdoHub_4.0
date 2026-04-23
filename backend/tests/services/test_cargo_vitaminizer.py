import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
from app.services.cargo_vitaminizer import CargoVitaminizerAgent, MappingDiscovery, GlobalMetadata
from app.schemas.edital_schema import Cargo, EditalGeral, CargoIdentificado


_CARGOS_ID = [
    CargoIdentificado(titulo="Analista Judiciário", codigo_edital="01"),
    CargoIdentificado(titulo="Técnico Judiciário", codigo_edital="02"),
]

_TABLE_MD = """\
| Cargo | AC | PcD | Total |
|-------|-----|-----|-------|
| Analista Judiciário | 10 | 2 | 12 |
| Técnico Judiciário | 20 | 3 | 23 |
"""


# ── _process_single_table ────────────────────────────────────────────────────

def test_process_single_table_short_table_skipped():
    agent = CargoVitaminizerAgent()
    discovery = MappingDiscovery(acronyms={}, regions={}, headers=[])
    cargo_totals = {"Analista": {"vagas_ac": 0}}
    agent._process_single_table("| A |\n| 1 |", discovery, [], cargo_totals)
    # Should not raise, just return early


def test_process_single_table_without_pipe_skipped():
    agent = CargoVitaminizerAgent()
    discovery = MappingDiscovery(acronyms={}, regions={}, headers=[])
    agent._process_single_table("no pipes here", discovery, [], {})


def test_process_single_table_malformed_handled_gracefully():
    agent = CargoVitaminizerAgent()
    discovery = MappingDiscovery(acronyms={"AC": "vagas_ac"}, regions={}, headers=[])
    cargo_totals = {}
    agent._process_single_table("|||bad|||data", discovery, _CARGOS_ID, cargo_totals)


# ── _aggregate_vacancies ─────────────────────────────────────────────────────

def test_aggregate_vacancies_empty_tables():
    agent = CargoVitaminizerAgent()
    discovery = MappingDiscovery(acronyms={}, regions={}, headers=[])
    result = agent._aggregate_vacancies([], discovery, _CARGOS_ID)
    assert "Analista Judiciário" in result
    assert result["Analista Judiciário"]["vagas_ac"] == 0


def test_aggregate_vacancies_processes_tables():
    agent = CargoVitaminizerAgent()
    discovery = MappingDiscovery(
        acronyms={"AC": "vagas_ac"},
        regions={},
        headers=["Cargo"],
    )
    result = agent._aggregate_vacancies([_TABLE_MD], discovery, _CARGOS_ID)
    assert isinstance(result, dict)


# ── _discover_structure ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_discover_structure_success():
    agent = CargoVitaminizerAgent()
    mock_mapping = MappingDiscovery(
        acronyms={"AC": "vagas_ac"}, regions={"01": "Analista"}, headers=["Cargo"]
    )
    with patch.object(agent.ollama_provider, 'generate_json',
                      new_callable=AsyncMock, return_value=mock_mapping):
        result = await agent._discover_structure("Texto do edital", [_TABLE_MD])
        assert result.acronyms == {"AC": "vagas_ac"}


@pytest.mark.asyncio
async def test_discover_structure_provider_failure_returns_empty():
    agent = CargoVitaminizerAgent()
    with patch.object(agent.ollama_provider, 'generate_json',
                      new_callable=AsyncMock,
                      side_effect=Exception("LLM offline")):
        result = await agent._discover_structure("Texto", [])
        assert result.acronyms == {}
        assert result.regions == {}


# ── _extract_global_metadata ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_extract_global_metadata_success():
    agent = CargoVitaminizerAgent()
    mock_meta = GlobalMetadata(
        edital_info=EditalGeral(orgao="TRT", banca="CESPE"),
        salary_patterns=["R$ 8.000,00"],
    )
    with patch.object(agent.ollama_provider, 'generate_json',
                      new_callable=AsyncMock, return_value=mock_meta):
        result = await agent._extract_global_metadata("Texto do edital")
        assert result.edital_info.orgao == "TRT"


@pytest.mark.asyncio
async def test_extract_global_metadata_failure_returns_default():
    agent = CargoVitaminizerAgent()
    with patch.object(agent.ollama_provider, 'generate_json',
                      new_callable=AsyncMock,
                      side_effect=Exception("LLM error")):
        result = await agent._extract_global_metadata("Texto")
        assert result.edital_info.orgao == "Pendente"
        assert result.salary_patterns == []


# ── vitaminize ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_vitaminize_full_flow(tmp_path):
    agent = CargoVitaminizerAgent()
    content_hash = "vitamin-hash"
    storage_path = tmp_path / content_hash
    (storage_path / "tables").mkdir(parents=True)
    (storage_path / "main.md").write_text("Edital completo.", encoding="utf-8")
    (storage_path / "tables" / "tabela_0.md").write_text(_TABLE_MD, encoding="utf-8")

    mock_discovery = MappingDiscovery(acronyms={}, regions={}, headers=[])
    mock_meta = GlobalMetadata(
        edital_info=EditalGeral(orgao="TRT", banca="CESPE"),
        salary_patterns=["R$ 8.000,00"],
    )

    with patch.object(agent, '_discover_structure',
                      new_callable=AsyncMock, return_value=mock_discovery), \
         patch.object(agent, '_extract_global_metadata',
                      new_callable=AsyncMock, return_value=mock_meta), \
         patch('app.services.cargo_vitaminizer.Path') as mock_path_cls:

        mock_path_cls.return_value.__truediv__ = lambda self, o: storage_path / o if o == content_hash else storage_path / o
        mock_path_cls.return_value.exists.return_value = False

        # Patch with real path
        with patch('app.services.cargo_vitaminizer.Path',
                   side_effect=lambda *a: tmp_path if "storage" in str(a[0]) else Path(*a)):
            result = await agent.vitaminize(content_hash, _CARGOS_ID)
            assert isinstance(result.cargos_vitaminados, list)


@pytest.mark.asyncio
async def test_vitaminize_filters_noise_cargos(tmp_path):
    agent = CargoVitaminizerAgent()
    content_hash = "noise-hash"
    storage_path = tmp_path / content_hash
    storage_path.mkdir()
    (storage_path / "main.md").write_text("Edital.", encoding="utf-8")
    (storage_path / "tables").mkdir()

    noisy_cargos = [
        CargoIdentificado(titulo="Total", codigo_edital=None),
        CargoIdentificado(titulo="Jurado", codigo_edital=None),
        CargoIdentificado(titulo="Analista Judiciário", codigo_edital="01"),
    ]

    mock_discovery = MappingDiscovery(acronyms={}, regions={}, headers=[])
    mock_meta = GlobalMetadata(
        edital_info=EditalGeral(orgao="TRT", banca="CESPE"),
        salary_patterns=[],
    )

    with patch.object(agent, '_discover_structure',
                      new_callable=AsyncMock, return_value=mock_discovery), \
         patch.object(agent, '_extract_global_metadata',
                      new_callable=AsyncMock, return_value=mock_meta), \
         patch('app.services.cargo_vitaminizer.Path',
               side_effect=lambda *a: tmp_path if "storage" in str(a[0]) else Path(*a)):

        result = await agent.vitaminize(content_hash, noisy_cargos)
        titles = [c.titulo for c in result.cargos_vitaminados]
        assert "Total" not in titles
        assert "Jurado" not in titles
        assert "Analista Judiciário" in titles
