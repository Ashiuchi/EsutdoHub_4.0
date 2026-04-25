import pytest
from unittest.mock import MagicMock, patch
from app.providers.groq_provider import GroqProvider
from app.providers.openrouter_provider import OpenRouterProvider
from app.providers.nvidia_provider import NVIDIAProvider
from app.services.ai_service import AIService
from app.core.config import settings

def test_providers_initialization():
    # Test Groq
    with patch("app.core.config.settings.groq_api_key", "test-key"):
        provider = GroqProvider()
        assert provider.api_key == "test-key"
        assert provider.base_url == "https://api.groq.com/openai/v1"

    # Test OpenRouter
    with patch("app.core.config.settings.openrouter_api_key", "test-key"):
        provider = OpenRouterProvider()
        assert provider.api_key == "test-key"
        assert "X-Title" in provider.extra_headers

    # Test NVIDIA
    with patch("app.core.config.settings.nvidia_api_key", "test-key"):
        provider = NVIDIAProvider()
        assert provider.api_key == "test-key"

def test_ai_service_provider_chain():
    # Mock settings to have all keys
    with patch("app.core.config.settings.groq_api_key", "key1"), \
         patch("app.core.config.settings.gemini_api_key", "key2"), \
         patch("app.core.config.settings.nvidia_api_key", "key3"), \
         patch("app.core.config.settings.openrouter_api_key", "key4"), \
         patch("app.core.config.settings.llm_strategy", "local_first"):
        
        service = AIService()
        chain = service._get_provider_chain()
        
        # Order: Ollama -> Groq -> NVIDIA -> OpenRouter -> Gemini
        assert len(chain) == 5
        assert chain[0].__class__.__name__ == "OllamaProvider"
        assert chain[1].__class__.__name__ == "GroqProvider"
        assert chain[2].__class__.__name__ == "NVIDIAProvider"
        assert chain[3].__class__.__name__ == "OpenRouterProvider"
        assert chain[4].__class__.__name__ == "GeminiProvider"

def test_ai_service_skips_missing_keys():
    # Only Groq and OpenRouter
    with patch("app.core.config.settings.groq_api_key", "key1"), \
         patch("app.core.config.settings.gemini_api_key", None), \
         patch("app.core.config.settings.nvidia_api_key", None), \
         patch("app.core.config.settings.openrouter_api_key", "key2"), \
         patch("app.core.config.settings.llm_strategy", "local_first"):
        
        service = AIService()
        chain = service._get_provider_chain()
        
        assert len(chain) == 3
        assert chain[0].__class__.__name__ == "OllamaProvider"
        assert chain[1].__class__.__name__ == "GroqProvider"
        assert chain[2].__class__.__name__ == "OpenRouterProvider"
