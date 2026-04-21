import pytest
import asyncio
import json
from unittest.mock import patch, AsyncMock
from pydantic import BaseModel, ValidationError

from app.providers.ollama_provider import OllamaProvider
from app.core.config import settings


class TestSchema(BaseModel):
    name: str
    age: int


@pytest.mark.asyncio
async def test_ollama_provider_initialization():
    """OllamaProvider should initialize with correct defaults"""
    provider = OllamaProvider()
    assert provider.base_url == settings.ollama_url
    assert provider.model == "llama3.1:8b"
    assert provider.timeout == settings.ollama_timeout


@pytest.mark.asyncio
async def test_ollama_provider_successful_json_generation():
    """OllamaProvider should successfully generate and validate JSON"""
    provider = OllamaProvider()

    mock_response = '{"name": "John", "age": 30}'

    with patch('aiohttp.ClientSession.post') as mock_post:
        mock_response_obj = AsyncMock()
        mock_response_obj.json.return_value = {"response": mock_response}
        mock_post.return_value.__aenter__.return_value = mock_response_obj

        result = await provider.generate_json(
            prompt="Generate a person",
            schema=TestSchema
        )

        assert result.name == "John"
        assert result.age == 30


@pytest.mark.asyncio
async def test_ollama_provider_connection_error():
    """OllamaProvider should raise ConnectionError when unavailable"""
    provider = OllamaProvider()

    with patch('aiohttp.ClientSession.post', side_effect=ConnectionError("Connection refused")):
        with pytest.raises(ConnectionError):
            await provider.generate_json(
                prompt="Test",
                schema=TestSchema
            )


@pytest.mark.asyncio
async def test_ollama_provider_invalid_json():
    """OllamaProvider should raise ValueError for invalid JSON"""
    provider = OllamaProvider()

    with patch('aiohttp.ClientSession.post') as mock_post:
        mock_response_obj = AsyncMock()
        mock_response_obj.json.return_value = {"response": "not valid json {"}
        mock_post.return_value.__aenter__.return_value = mock_response_obj

        with pytest.raises(ValueError):
            await provider.generate_json(
                prompt="Test",
                schema=TestSchema
            )


@pytest.mark.asyncio
async def test_ollama_provider_schema_validation_error():
    """OllamaProvider should raise ValidationError for non-matching schema"""
    provider = OllamaProvider()

    # Response missing required 'age' field
    mock_response = '{"name": "John"}'

    with patch('aiohttp.ClientSession.post') as mock_post:
        mock_response_obj = AsyncMock()
        mock_response_obj.json.return_value = {"response": mock_response}
        mock_post.return_value.__aenter__.return_value = mock_response_obj

        with pytest.raises(ValidationError):
            await provider.generate_json(
                prompt="Test",
                schema=TestSchema
            )


@pytest.mark.asyncio
async def test_ollama_provider_timeout():
    """OllamaProvider should raise TimeoutError on timeout"""
    provider = OllamaProvider(timeout=1)

    with patch('aiohttp.ClientSession.post', side_effect=asyncio.TimeoutError()):
        with pytest.raises(TimeoutError):
            await provider.generate_json(
                prompt="Test",
                schema=TestSchema
            )
