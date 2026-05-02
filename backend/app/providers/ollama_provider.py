import logging
import aiohttp
import asyncio
from typing import List, Optional, Type, TypeVar
from pydantic import BaseModel

from .base_provider import BaseLLMProvider
from app.core.config import settings

T = TypeVar('T', bound=BaseModel)
logger = logging.getLogger(__name__)

EMBED_MODEL = "bge-m3"


class OllamaProvider(BaseLLMProvider):
    """Local Ollama LLM provider"""

    def __init__(self, base_url: str = None, model: str = None, timeout: int = None):
        self.base_url = (base_url or settings.ollama_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.timeout = timeout or settings.ollama_timeout
        logger.info(f"OllamaProvider initialized: {self.base_url}, model={self.model}, timeout={self.timeout}s")

    async def embed_text(
        self,
        text: str,
        model_name: str = EMBED_MODEL,
    ) -> List[float]:
        """Gera embedding via Ollama /api/embeddings (nomic-embed-text → 768d)."""
        if not text or not text.strip():
            raise ValueError("embed_text: texto vazio")

        url = f"{self.base_url}/api/embeddings"
        payload = {"model": model_name, "prompt": text}

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=120)
            ) as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        body = await response.text()
                        raise ConnectionError(
                            f"Ollama embed HTTP {response.status}: {body[:200]}"
                        )
                    data = await response.json()
                    embedding: List[float] = data["embedding"]
                    return embedding
        except aiohttp.ClientConnectorError as exc:
            raise ConnectionError(f"Ollama não acessível em {self.base_url}: {exc}") from exc
        except aiohttp.ClientError as exc:
            raise ConnectionError(f"Ollama embed falhou: {exc}") from exc

    async def generate_json(self, prompt: str, schema: Type[T]) -> T:
        """Generate JSON response from Ollama local model"""
        logger.info(f"OllamaProvider: Starting JSON generation for schema {schema.__name__}")

        payload = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False
        }

        url = f"{self.base_url}/api/generate"

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                logger.debug(f"Sending request to {url}")
                async with session.post(url, json=payload) as response:
                    data = await response.json()
                    response_text = data.get("response", "")
                    logger.info(f"OllamaProvider: Received response ({len(response_text)} chars)")

        except asyncio.TimeoutError:
            logger.error(f"OllamaProvider: Timeout after {self.timeout}s")
            raise TimeoutError(f"Ollama request timed out after {self.timeout}s")
        except aiohttp.ClientConnectorError as e:
            logger.error(f"OllamaProvider: Connection error - {e}")
            raise ConnectionError(f"Failed to connect to Ollama at {self.base_url}: {e}")
        except aiohttp.ClientError as e:
            logger.error(f"OllamaProvider: Request error - {e}")
            raise ConnectionError(f"Ollama request failed: {e}")

        # Validate response against schema
        try:
            result = self._validate_json_response(response_text, schema)
            logger.info(f"OllamaProvider: Successfully validated response for {schema.__name__}")
            return result
        except Exception as e:
            logger.error(f"OllamaProvider: Validation failed - {e}. Raw response: {response_text[:1000]}")
            raise
