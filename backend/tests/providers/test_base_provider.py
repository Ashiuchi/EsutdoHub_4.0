import pytest
from abc import ABC
from pydantic import BaseModel
from app.providers.base_provider import BaseLLMProvider


class SampleSchema(BaseModel):
    title: str
    description: str


def test_base_llm_provider_is_abstract():
    """BaseLLMProvider should be abstract and not instantiable"""
    assert issubclass(BaseLLMProvider, ABC)

    with pytest.raises(TypeError):
        BaseLLMProvider()


@pytest.mark.asyncio
async def test_base_llm_provider_has_generate_json_method():
    """BaseLLMProvider must define generate_json async method"""
    assert hasattr(BaseLLMProvider, 'generate_json')
    assert callable(getattr(BaseLLMProvider, 'generate_json'))
