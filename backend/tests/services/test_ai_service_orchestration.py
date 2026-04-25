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
    # Patch the CLASSES before instantiating AIService
    with patch("app.services.ai_service.CargoTitleAgent") as mock_cargo_cls, \
         patch("app.services.ai_service.CargoVitaminizerAgent") as mock_vit_cls, \
         patch("app.services.ai_service.SubjectsScoutAgent") as mock_scout_cls:
        
        # Setup mocks
        mock_cargo_agent = mock_cargo_cls.return_value
        mock_vit_agent = mock_vit_cls.return_value
        mock_scout_agent = mock_scout_cls.return_value

        mock_cargo_agent.hunt_titles = AsyncMock(return_value=[CargoIdentificado(titulo="Analista", codigo_edital="01")])
        
        from app.services.cargo_vitaminizer import VitaminData
        fake_vitamin = VitaminData(
            edital_info=EditalGeral(orgao="Org", banca="Banca"),
            cargos_vitaminados=[Cargo(titulo="Analista")]
        )
        mock_vit_agent.vitaminize = AsyncMock(return_value=fake_vitamin)
        
        final_cargos = [Cargo(titulo="Analista", materias=[Materia(nome="Math", topicos=["Algebra"])])]
        mock_scout_agent.scout = AsyncMock(return_value=final_cargos)

        service = AIService()
        chain = [MagicMock(spec=BaseLLMProvider)]
        
        with patch.object(service, "_get_provider_chain", return_value=chain):
            result = await service.process_edital("abc123", "markdown content")

        assert result["edital"].orgao == "Org"
        assert len(result["cargos"]) == 1
        mock_cargo_agent.hunt_titles.assert_awaited_once_with("abc123", chain)
        mock_vit_agent.vitaminize.assert_awaited_once_with("abc123", mock_cargo_agent.hunt_titles.return_value, chain)
        mock_scout_agent.scout.assert_awaited_once_with("abc123", fake_vitamin.cargos_vitaminados, chain)


@pytest.mark.asyncio
async def test_process_edital_returns_empty_cargos_when_all_fail():
    with patch("app.services.ai_service.CargoTitleAgent") as mock_cargo_cls, \
         patch("app.services.ai_service.CargoVitaminizerAgent") as mock_vit_cls, \
         patch("app.services.ai_service.SubjectsScoutAgent") as mock_scout_cls:
        
        mock_cargo_agent = mock_cargo_cls.return_value
        mock_vit_agent = mock_vit_cls.return_value
        mock_scout_agent = mock_scout_cls.return_value

        mock_cargo_agent.hunt_titles = AsyncMock(return_value=[])
        
        from app.services.cargo_vitaminizer import VitaminData
        fake_vitamin = VitaminData(
            edital_info=EditalGeral(orgao="Org", banca="Banca"),
            cargos_vitaminados=[]
        )
        mock_vit_agent.vitaminize = AsyncMock(return_value=fake_vitamin)
        mock_scout_agent.scout = AsyncMock(return_value=[])

        service = AIService()
        with patch.object(service, "_get_provider_chain", return_value=[]):
            result = await service.process_edital("abc123", "markdown content")

        assert result["cargos"] == []
