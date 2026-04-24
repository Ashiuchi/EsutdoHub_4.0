import logging
import aiohttp
import asyncio
from typing import Type, TypeVar, Dict, Any, Optional
from pydantic import BaseModel

from .base_provider import BaseLLMProvider

T = TypeVar('T', bound=BaseModel)
logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(BaseLLMProvider):
    """Generic provider for OpenAI-compatible APIs (Groq, OpenRouter, NVIDIA, etc.)"""

    def __init__(
        self, 
        name: str,
        api_key: str, 
        base_url: str, 
        model: str, 
        timeout: int = 30,
        extra_headers: Optional[Dict[str, str]] = None
    ):
        self.name = name
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout = timeout
        self.extra_headers = extra_headers or {}
        logger.info(f"{self.name}Provider initialized: model={self.model}, timeout={self.timeout}s")

    async def generate_json(self, prompt: str, schema: Type[T]) -> T:
        """Generate JSON response using OpenAI-compatible chat completion endpoint"""
        logger.info(f"{self.name}Provider: Starting JSON generation for schema {schema.__name__}")

        if not self.api_key:
            raise ConnectionError(f"{self.name}Provider not configured - missing API key")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **self.extra_headers
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }

        url = f"{self.base_url}/chat/completions"

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                logger.debug(f"Sending request to {url}")
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"{self.name}Provider: API error {response.status} - {error_text}")
                        raise ConnectionError(f"{self.name} API error: {response.status}")
                    
                    data = await response.json()
                    response_text = data["choices"][0]["message"]["content"]
                    logger.info(f"{self.name}Provider: Received response ({len(response_text)} chars)")

        except asyncio.TimeoutError:
            logger.error(f"{self.name}Provider: Timeout after {self.timeout}s")
            raise TimeoutError(f"{self.name} request timed out after {self.timeout}s")
        except Exception as e:
            logger.error(f"{self.name}Provider: Request error - {e}")
            raise ConnectionError(f"{self.name} request failed: {e}")

        # Validate response against schema
        try:
            result = self._validate_json_response(response_text, schema)
            logger.info(f"{self.name}Provider: Successfully validated response for {schema.__name__}")
            return result
        except Exception as e:
            logger.error(f"{self.name}Provider: Validation failed - {e}")
            raise
