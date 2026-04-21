import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from pydantic import BaseModel

from app.services.ai_service import AIService
from app.core.config import settings
from app.schemas.edital_schema import EditalGeral, Cargo, Materia


@pytest.mark.asyncio
async def test_ai_service_local_first_success():
    """AIService should use Ollama first with local_first strategy"""
    service = AIService()

    mock_edital = EditalGeral(
        orgao="Test Org",
        banca="Test Bank",
        data_prova=None,
        periodo_inscricao=None,
        link_edital=None,
        cargos=[
            Cargo(
                titulo="Test Position",
                vagas_ampla=5,
                vagas_cotas=2,
                salario=3000.0,
                requisitos="Test requirements",
                materias=[Materia(nome="Math", topicos=["Algebra"])]
            )
        ]
    )

    with patch.object(service.ollama_provider, 'generate_json', new_callable=AsyncMock) as mock_ollama:
        mock_ollama.return_value = mock_edital

        result = await service.extract_edital_data(md_content="Test content")

        assert result.orgao == "Test Org"
        mock_ollama.assert_called_once()


@pytest.mark.asyncio
async def test_ai_service_local_first_fallback_to_gemini():
    """AIService should fallback to Gemini when Ollama fails"""
    service = AIService()

    mock_edital = EditalGeral(
        orgao="Test Org",
        banca="Test Bank",
        data_prova=None,
        periodo_inscricao=None,
        link_edital=None,
        cargos=[]
    )

    with patch.object(service.ollama_provider, 'generate_json', new_callable=AsyncMock) as mock_ollama, \
         patch.object(service.gemini_provider, 'generate_json', new_callable=AsyncMock) as mock_gemini:

        mock_ollama.side_effect = ConnectionError("Ollama unavailable")
        mock_gemini.return_value = mock_edital

        result = await service.extract_edital_data(md_content="Test content")

        assert result.orgao == "Test Org"
        mock_gemini.assert_called_once()


@pytest.mark.asyncio
async def test_ai_service_local_only_fails_without_fallback():
    """AIService should fail immediately with local_only strategy if Ollama unavailable"""
    with patch('app.services.ai_service.settings') as mock_settings:
        mock_settings.llm_strategy = "local_only"
        mock_settings.gemini_api_key = "test-key"
        mock_settings.ollama_url = "http://localhost:11434"
        mock_settings.cloud_fallback = True

        service = AIService()

        with patch.object(service.ollama_provider, 'generate_json', new_callable=AsyncMock) as mock_ollama:
            mock_ollama.side_effect = ConnectionError("Ollama unavailable")

            with pytest.raises(RuntimeError, match="All LLM providers failed"):
                await service.extract_edital_data(md_content="Test content")

            mock_ollama.assert_called_once()


@pytest.mark.asyncio
async def test_ai_service_cloud_only_uses_gemini():
    """AIService should use only Gemini with cloud_only strategy"""
    with patch('app.services.ai_service.settings') as mock_settings:
        mock_settings.llm_strategy = "cloud_only"
        mock_settings.gemini_api_key = "test-key"
        mock_settings.ollama_url = "http://localhost:11434"

        service = AIService()

        mock_edital = EditalGeral(
            orgao="Cloud Org",
            banca="Cloud Bank",
            data_prova=None,
            periodo_inscricao=None,
            link_edital=None,
            cargos=[]
        )

        with patch.object(service.gemini_provider, 'generate_json', new_callable=AsyncMock) as mock_gemini:
            mock_gemini.return_value = mock_edital

            result = await service.extract_edital_data(md_content="Test content")

            assert result.orgao == "Cloud Org"
            mock_gemini.assert_called_once()


@pytest.mark.asyncio
async def test_ai_service_all_providers_exhausted():
    """AIService should raise error when all providers fail"""
    service = AIService()

    with patch.object(service.ollama_provider, 'generate_json', new_callable=AsyncMock) as mock_ollama, \
         patch.object(service.gemini_provider, 'generate_json', new_callable=AsyncMock) as mock_gemini:

        mock_ollama.side_effect = ConnectionError("Ollama down")
        mock_gemini.side_effect = ConnectionError("Gemini down")

        with pytest.raises(RuntimeError, match="All LLM providers failed"):
            await service.extract_edital_data(md_content="Test content")
