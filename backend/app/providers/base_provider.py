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
        Includes "Lenient Parsing" to handle common LLM key naming mismatches.
        """
        import json

        # Clean up markdown code blocks if present
        cleaned = response_text.strip().replace('```json', '').replace('```', '').strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}\nResponse was: {cleaned[:200]}")
            raise ValueError(f"Invalid JSON response: {e}")

        # --- Lenient Parsing Logic ---
        # Map common mismatches between LLM output and our Pydantic schemas
        aliases = {
            "edital_info": ["edital", "edital_geral", "info"],
            "cargos": ["cargos_extraidos", "lista_cargos"],
            "materias": ["conteudo", "disciplinas"],
            "topicos": ["assuntos", "lista_topicos"]
        }

        if isinstance(data, dict):
            # Recursively unwrap if the LLM wrapped the response in keys named after schemas
            def unwrap(d, target_schema):
                if not isinstance(d, dict) or len(d) != 1:
                    return d
                
                key = list(d.keys())[0]
                # Check if key matches current schema or any field schema
                if key.lower() == target_schema.__name__.lower():
                    logger.info(f"Unwrapping LLM response from root key '{key}'")
                    return unwrap(d[key], target_schema)
                
                return d

            data = unwrap(data, schema)

            # Also check for common field-level wrapping (like edital_info: { EditalGeral: { ... } })
            for key, value in data.items():
                if isinstance(value, dict) and len(value) == 1:
                    # If the key is a field in the schema, try to unwrap its value
                    field = schema.model_fields.get(key)
                    if field and hasattr(field.annotation, "__name__"):
                        field_schema_name = field.annotation.__name__
                        inner_key = list(value.keys())[0]
                        if inner_key.lower() == field_schema_name.lower():
                            logger.info(f"Unwrapping field '{key}' from inner key '{inner_key}'")
                            data[key] = value[inner_key]

            for target_key, possible_aliases in aliases.items():
                if target_key not in data:
                    for alias in possible_aliases:
                        if alias in data:
                            logger.info(f"Lenient Parsing: Mapping alias '{alias}' to target key '{target_key}'")
                            data[target_key] = data.pop(alias)
                            break

        try:
            return schema(**data)
        except ValidationError as e:
            logger.error(f"Schema validation error: {e}")
            raise
