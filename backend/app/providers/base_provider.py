import logging
from abc import ABC, abstractmethod
from typing import Type, TypeVar
from pydantic import BaseModel, ValidationError

T = TypeVar('T', bound=BaseModel)
logger = logging.getLogger(__name__)


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers (Ollama, Gemini, etc)"""

    @abstractmethod
    async def generate_json(self, prompt: str, schema: Type[T]) -> T:
        """
        Generate a response from the LLM and validate against schema.

        Args:
            prompt: The input prompt for the LLM
            schema: A Pydantic model class to validate response against

        Returns:
            Instance of schema class with validated data

        Raises:
            ConnectionError: If provider is unavailable
            ValidationError: If response doesn't match schema
            TimeoutError: If request exceeds timeout
        """
        pass

    def _validate_json_response(self, response_text: str, schema: Type[T]) -> T:
        """
        Parse and validate JSON response against Pydantic schema.

        Args:
            response_text: Raw text response from LLM
            schema: Pydantic model class to validate against

        Returns:
            Validated instance of schema

        Raises:
            ValidationError: If JSON doesn't match schema
        """
        import json

        # Clean up markdown code blocks if present
        cleaned = response_text.strip().replace('```json', '').replace('```', '').strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}\nResponse was: {cleaned[:200]}")
            raise ValueError(f"Invalid JSON response: {e}")

        try:
            return schema(**data)
        except ValidationError as e:
            logger.error(f"Schema validation error: {e}")
            raise
