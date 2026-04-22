import logging
import asyncio
from typing import Type, TypeVar
from pydantic import BaseModel
import google.generativeai as genai

from .base_provider import BaseLLMProvider
from app.core.config import settings

T = TypeVar('T', bound=BaseModel)
logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    """Cloud-based Google Gemini LLM provider"""

    def __init__(self, api_key: str = None, model_name: str = "gemini-2.0-flash", timeout: int = None):
        self.api_key = api_key or settings.gemini_api_key
        self.model_name = model_name
        self.timeout = timeout or settings.gemini_timeout

        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(model_name)
        else:
            self.model = None
            logger.warning("GeminiProvider: No API key configured")

        logger.info(f"GeminiProvider initialized: model={self.model_name}, timeout={self.timeout}s")

    async def generate_json(self, prompt: str, schema: Type[T]) -> T:
        """Generate JSON response from Gemini"""
        logger.info(f"GeminiProvider: Starting JSON generation for schema {schema.__name__}")

        if not self.model:
            raise ConnectionError("GeminiProvider not configured - missing API key")

        try:
            # Gemini API is synchronous, run it in executor to avoid blocking
            loop = asyncio.get_running_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self.model.generate_content(prompt)
                ),
                timeout=self.timeout
            )

            response_text = response.text
            logger.info(f"GeminiProvider: Received response ({len(response_text)} chars)")

        except asyncio.TimeoutError:
            logger.error(f"GeminiProvider: Timeout after {self.timeout}s")
            raise TimeoutError(f"Gemini request timed out after {self.timeout}s")
        except Exception as e:
            logger.error(f"GeminiProvider: Request error - {e}")
            raise ConnectionError(f"Gemini request failed: {e}")

        # Validate response against schema
        try:
            result = self._validate_json_response(response_text, schema)
            logger.info(f"GeminiProvider: Successfully validated response for {schema.__name__}")
            return result
        except Exception as e:
            logger.error(f"GeminiProvider: Validation failed - {e}")
            raise
