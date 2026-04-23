import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pydantic import BaseModel

from app.providers.gemini_provider import GeminiProvider


class SimpleSchema(BaseModel):
    value: str


@pytest.mark.asyncio
async def test_gemini_no_api_key_sets_model_none():
    with patch('app.providers.gemini_provider.settings') as mock_settings:
        mock_settings.gemini_api_key = None
        mock_settings.gemini_timeout = 15
        provider = GeminiProvider(api_key=None)
        assert provider.model is None


@pytest.mark.asyncio
async def test_gemini_no_model_raises_connection_error():
    provider = GeminiProvider.__new__(GeminiProvider)
    provider.model = None
    provider.timeout = 15
    provider.model_name = "gemini-2.0-flash"

    with pytest.raises(ConnectionError, match="missing API key"):
        await provider.generate_json("prompt", SimpleSchema)


@pytest.mark.asyncio
async def test_gemini_timeout_raises_timeout_error():
    provider = GeminiProvider.__new__(GeminiProvider)
    provider.timeout = 1
    provider.model_name = "gemini-2.0-flash"
    mock_model = MagicMock()
    mock_model.generate_content.side_effect = lambda p: asyncio.sleep(999)
    provider.model = mock_model

    with patch('asyncio.wait_for', side_effect=asyncio.TimeoutError()):
        with pytest.raises(TimeoutError, match="timed out"):
            await provider.generate_json("prompt", SimpleSchema)


@pytest.mark.asyncio
async def test_gemini_request_exception_raises_connection_error():
    provider = GeminiProvider.__new__(GeminiProvider)
    provider.timeout = 15
    provider.model_name = "gemini-2.0-flash"
    mock_model = MagicMock()
    mock_model.generate_content.side_effect = Exception("API error")
    provider.model = mock_model

    with patch('asyncio.wait_for', side_effect=Exception("API error")):
        with pytest.raises(ConnectionError, match="Gemini request failed"):
            await provider.generate_json("prompt", SimpleSchema)
