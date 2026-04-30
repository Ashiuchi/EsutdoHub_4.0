import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock
from app.services.cargo_vitaminizer import (
    CargoVitaminizerAgent,
    MappingDiscovery,
    GlobalDNA,
    CargoDNA,
)
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


def test_process_single_table_without_pipe_skipped():
    agent = CargoVitaminizerAgent()
    discovery = MappingDiscovery(acronyms={}, regions={}, headers=[])
    agent._process_single_table("no pipes here", discovery, [], {})


def test_process_single_table_malformed_handled_gracefully():
    agent = CargoVitaminizerAgent()
    discovery = MappingDiscovery(acronyms={"AC": "vagas_ac"}, regions={}, headers=[])
    agent._process_single_table("|||bad|||data", discovery, _CARGOS_ID, {})


# ── _aggregate_vacancies ─────────────────────────────────────────────────────

def test_aggregate_vacancies_empty_tables():
    agent = CargoVitaminizerAgent()
    discovery = MappingDiscovery(acronyms={}, regions={}, headers=[])
    result = agent._aggregate_vacancies([], discovery, _CARGOS_ID)
    assert "Analista Judiciário" in result
    assert result["Analista Judiciário"]["vagas_ac"] == 0


def test_aggregate_vacancies_processes_tables():
    agent = CargoVitaminizerAgent()
    discovery = MappingDiscovery(acronyms={"AC": "vagas_ac"}, regions={}, headers=["Cargo"])
    result = agent._aggregate_vacancies([_TABLE_MD], discovery, _CARGOS_ID)
    assert isinstance(result, dict)


# ── _discover_structure ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_discover_structure_success():
    agent = CargoVitaminizerAgent()
    mock_mapping = MappingDiscovery(
        acronyms={"AC": "vagas_ac"}, regions={"01": "Analista"}, headers=["Cargo"]
    )
    with patch.object(agent.ollama_provider, "generate_json",
                      new_callable=AsyncMock, return_value=mock_mapping):
        result = await agent._discover_structure("Texto do edital", [_TABLE_MD])
        assert result.acronyms == {"AC": "vagas_ac"}


@pytest.mark.asyncio
async def test_discover_structure_provider_failure_returns_empty():
    agent = CargoVitaminizerAgent()
    with patch.object(agent.ollama_provider, "generate_json",
                      new_callable=AsyncMock, side_effect=Exception("LLM offline")):
        result = await agent._discover_structure("Texto", [])
        assert result.acronyms == {}
        assert result.regions == {}


# ── _extract_global_dna ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_extract_global_dna_success():
    agent = CargoVitaminizerAgent()
    mock_dna = GlobalDNA(
        orgao="TRT",
        banca="CESPE",
        data_prova="15/06/2025",
        inscription_start="01/04/2025",
        inscription_end="30/04/2025",
        fee=85.0,
        salary_patterns=["R$ 8.000,00"],
    )
    with patch.object(agent.ollama_provider, "generate_json",
                      new_callable=AsyncMock, return_value=mock_dna):
        result = await agent._extract_global_dna("Texto do edital")
        assert result.orgao == "TRT"
        assert result.fee == 85.0
        assert result.salary_patterns == ["R$ 8.000,00"]


@pytest.mark.asyncio
async def test_extract_global_dna_failure_returns_default():
    agent = CargoVitaminizerAgent()
    with patch.object(agent.ollama_provider, "generate_json",
                      new_callable=AsyncMock, side_effect=Exception("LLM error")):
        result = await agent._extract_global_dna("Texto")
        assert result.orgao == "Pendente"
        assert result.salary_patterns == []


# ── _extract_cargo_dna ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_extract_cargo_dna_no_context_returns_default():
    agent = CargoVitaminizerAgent()
    result = await agent._extract_cargo_dna("Analista Judiciário", None)
    assert result.escolaridade == "Não informada"
    assert result.salario == 0.0


@pytest.mark.asyncio
async def test_extract_cargo_dna_success():
    agent = CargoVitaminizerAgent()
    mock_dna = CargoDNA(
        salario=12000.0,
        escolaridade="Ensino Superior em Direito",
        area="Area Judiciária",
        atribuicoes="Analisar, Instruir, Relatar",
        requisitos="Graduação em Direito, OAB ativo",
        lotation_cities="São Paulo",
        jornada="40h semanais",
    )
    with patch.object(agent.ollama_provider, "generate_json",
                      new_callable=AsyncMock, return_value=mock_dna):
        result = await agent._extract_cargo_dna("Analista Judiciário", "contexto do cargo")
        assert result.salario == 12000.0
        assert result.escolaridade == "Ensino Superior em Direito"


@pytest.mark.asyncio
async def test_extract_cargo_dna_failure_returns_default():
    agent = CargoVitaminizerAgent()
    with patch.object(agent.ollama_provider, "generate_json",
                      new_callable=AsyncMock, side_effect=Exception("LLM error")):
        result = await agent._extract_cargo_dna("Técnico", "algum contexto")
        assert result.salario == 0.0
        assert result.jornada == "Não informada"


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
    mock_global_dna = GlobalDNA(orgao="TRT", banca="CESPE", salary_patterns=["R$ 8.000,00"])
    mock_cargo_dna = CargoDNA(salario=8000.0, escolaridade="Superior")

    with patch.object(agent, "_discover_structure",
                      new_callable=AsyncMock, return_value=mock_discovery), \
         patch.object(agent, "_extract_global_dna",
                      new_callable=AsyncMock, return_value=mock_global_dna), \
         patch.object(agent, "_extract_cargo_dna",
                      new_callable=AsyncMock, return_value=mock_cargo_dna), \
         patch("app.services.cargo_vitaminizer.Path",
               side_effect=lambda *a: tmp_path if "storage" in str(a[0]) else Path(*a)):
        result = await agent.vitaminize(content_hash, _CARGOS_ID)
        assert isinstance(result.cargos_vitaminados, list)


@pytest.mark.asyncio
async def test_vitaminize_salary_priority_cargo_over_global(tmp_path):
    """CargoDNA.salario > 0 deve sobrepor GlobalDNA.salary_patterns."""
    agent = CargoVitaminizerAgent()
    content_hash = "salary-priority-hash"
    storage_path = tmp_path / content_hash
    (storage_path / "tables").mkdir(parents=True)
    (storage_path / "main.md").write_text("Edital.", encoding="utf-8")

    mock_discovery = MappingDiscovery(acronyms={}, regions={}, headers=[])
    mock_global_dna = GlobalDNA(orgao="TRT", banca="CESPE", salary_patterns=["R$ 5.000,00"])
    mock_cargo_dna = CargoDNA(salario=12000.0)

    with patch.object(agent, "_discover_structure",
                      new_callable=AsyncMock, return_value=mock_discovery), \
         patch.object(agent, "_extract_global_dna",
                      new_callable=AsyncMock, return_value=mock_global_dna), \
         patch.object(agent, "_extract_cargo_dna",
                      new_callable=AsyncMock, return_value=mock_cargo_dna), \
         patch("app.services.cargo_vitaminizer.Path",
               side_effect=lambda *a: tmp_path if "storage" in str(a[0]) else Path(*a)):
        result = await agent.vitaminize(content_hash, _CARGOS_ID)
        for cargo in result.cargos_vitaminados:
            assert cargo.salario == 12000.0, "Salário do cargo deve prevalecer sobre o global"


@pytest.mark.asyncio
async def test_vitaminize_salary_fallback_to_global(tmp_path):
    """CargoDNA.salario == 0.0 deve usar GlobalDNA.salary_patterns como fallback."""
    agent = CargoVitaminizerAgent()
    content_hash = "salary-fallback-hash"
    storage_path = tmp_path / content_hash
    (storage_path / "tables").mkdir(parents=True)
    (storage_path / "main.md").write_text("Edital.", encoding="utf-8")

    mock_discovery = MappingDiscovery(acronyms={}, regions={}, headers=[])
    mock_global_dna = GlobalDNA(orgao="TRT", banca="CESPE", salary_patterns=["R$ 5.000,00"])
    mock_cargo_dna = CargoDNA(salario=0.0)

    with patch.object(agent, "_discover_structure",
                      new_callable=AsyncMock, return_value=mock_discovery), \
         patch.object(agent, "_extract_global_dna",
                      new_callable=AsyncMock, return_value=mock_global_dna), \
         patch.object(agent, "_extract_cargo_dna",
                      new_callable=AsyncMock, return_value=mock_cargo_dna), \
         patch("app.services.cargo_vitaminizer.Path",
               side_effect=lambda *a: tmp_path if "storage" in str(a[0]) else Path(*a)):
        result = await agent.vitaminize(content_hash, _CARGOS_ID)
        for cargo in result.cargos_vitaminados:
            assert cargo.salario == 5000.0, "Deve usar salário global como fallback"


@pytest.mark.asyncio
async def test_vitaminize_with_cargo_contexts(tmp_path):
    """cargo_contexts deve ser repassado ao DNA Sniper."""
    agent = CargoVitaminizerAgent()
    content_hash = "ctx-hash"
    storage_path = tmp_path / content_hash
    storage_path.mkdir()
    (storage_path / "main.md").write_text("Edital.", encoding="utf-8")
    (storage_path / "tables").mkdir()

    contexts = {"Analista Judiciário": "O cargo requer graduação em Direito."}
    mock_discovery = MappingDiscovery(acronyms={}, regions={}, headers=[])
    mock_global_dna = GlobalDNA(orgao="TRT", banca="CESPE")
    mock_cargo_dna = CargoDNA(escolaridade="Superior em Direito")

    captured_contexts = []

    async def fake_extract_cargo_dna(titulo, context):
        captured_contexts.append((titulo, context))
        return mock_cargo_dna

    with patch.object(agent, "_discover_structure",
                      new_callable=AsyncMock, return_value=mock_discovery), \
         patch.object(agent, "_extract_global_dna",
                      new_callable=AsyncMock, return_value=mock_global_dna), \
         patch.object(agent, "_extract_cargo_dna", side_effect=fake_extract_cargo_dna), \
         patch("app.services.cargo_vitaminizer.Path",
               side_effect=lambda *a: tmp_path if "storage" in str(a[0]) else Path(*a)):
        await agent.vitaminize(content_hash, _CARGOS_ID, cargo_contexts=contexts)

    analista_call = next((c for t, c in captured_contexts if t == "Analista Judiciário"), None)
    assert analista_call == "O cargo requer graduação em Direito."
