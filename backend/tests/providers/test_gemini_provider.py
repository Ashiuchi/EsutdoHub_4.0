import pytest
from unittest.mock import patch, MagicMock
from pydantic import BaseModel, ValidationError

from app.providers.gemini_provider import GeminiProvider
from app.core.config import settings


class TestSchema(BaseModel):
    title: str
    content: str


@pytest.mark.asyncio
async def test_gemini_provider_initialization():
    """GeminiProvider should initialize with correct defaults"""
    provider = GeminiProvider()
    assert provider.timeout == settings.gemini_timeout
    assert provider.model_name == "gemini-2.0-flash"


@pytest.mark.asyncio
async def test_gemini_provider_successful_json_generation():
    """GeminiProvider should successfully generate and validate JSON"""
    provider = GeminiProvider()

    mock_response_text = '{"title": "Test", "content": "Description"}'

    with patch('google.generativeai.GenerativeModel') as mock_model_class:
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = mock_response_text
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model

        provider.model = mock_model

        result = await provider.generate_json(
            prompt="Generate content",
            schema=TestSchema
        )

        assert result.title == "Test"
        assert result.content == "Description"


@pytest.mark.asyncio
async def test_gemini_provider_invalid_json():
    """GeminiProvider should raise ValueError for invalid JSON"""
    provider = GeminiProvider()

    with patch('google.generativeai.GenerativeModel') as mock_model_class:
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "not valid json {"
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model

        provider.model = mock_model

        with pytest.raises(ValueError):
            await provider.generate_json(
                prompt="Test",
                schema=TestSchema
            )


@pytest.mark.asyncio
async def test_gemini_provider_schema_validation_error():
    """GeminiProvider should raise ValidationError for non-matching schema"""
    provider = GeminiProvider()

    # Missing 'content' required field
    mock_response_text = '{"title": "Test"}'

    with patch('google.generativeai.GenerativeModel') as mock_model_class:
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = mock_response_text
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model

        provider.model = mock_model

        with pytest.raises(ValidationError):
            await provider.generate_json(
                prompt="Test",
                schema=TestSchema
            )
