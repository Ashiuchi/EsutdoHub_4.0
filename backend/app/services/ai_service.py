import logging
from typing import TypeVar, List

from app.core.config import settings
from app.providers.ollama_provider import OllamaProvider
from app.providers.gemini_provider import GeminiProvider
from app.providers.base_provider import BaseLLMProvider
from app.schemas.edital_schema import EditalGeral

T = TypeVar('T')
logger = logging.getLogger(__name__)


class AIService:
    """Orchestrates LLM provider selection and failover strategy"""

    def __init__(self):
        self.ollama_provider = OllamaProvider()
        self.gemini_provider = GeminiProvider()
        self.strategy = settings.llm_strategy
        self.cloud_fallback = settings.cloud_fallback

        logger.info(f"AIService initialized with strategy={self.strategy}, cloud_fallback={self.cloud_fallback}")

    def _get_provider_chain(self) -> List[BaseLLMProvider]:
        """Build ordered list of providers based on strategy"""
        if self.strategy == "local_only":
            return [self.ollama_provider]
        elif self.strategy == "cloud_only":
            return [self.gemini_provider]
        elif self.strategy == "local_first":
            chain = [self.ollama_provider]
            if self.cloud_fallback:
                chain.append(self.gemini_provider)
            return chain
        else:
            logger.warning(f"Unknown strategy '{self.strategy}', defaulting to local_first")
            chain = [self.ollama_provider]
            if self.cloud_fallback:
                chain.append(self.gemini_provider)
            return chain

    async def extract_edital_data(self, md_content: str) -> EditalGeral:
        """Extract structured edital data from markdown content"""
        prompt = f'''
        Analise o edital abaixo e extraia os dados estruturados.
        Foque especialmente na separação por CARGOS. Cada cargo deve ter suas matérias e requisitos.
        Retorne APENAS o JSON puro seguindo este schema:
        {EditalGeral.model_json_schema()}

        EDITAL EM MARKDOWN:
        {md_content}
        '''

        providers = self._get_provider_chain()
        logger.info(f"extract_edital_data: Attempting with {len(providers)} provider(s): {[p.__class__.__name__ for p in providers]}")

        last_error = None
        for provider in providers:
            try:
                logger.info(f"extract_edital_data: Trying {provider.__class__.__name__}")
                result = await provider.generate_json(prompt=prompt, schema=EditalGeral)
                logger.info(f"extract_edital_data: ✓ Success with {provider.__class__.__name__}")
                return result

            except (ConnectionError, TimeoutError, ValueError) as e:
                last_error = e
                logger.warning(f"extract_edital_data: {provider.__class__.__name__} failed - {type(e).__name__}: {e}")
                continue
            except Exception as e:
                last_error = e
                logger.error(f"extract_edital_data: {provider.__class__.__name__} unexpected error - {e}")
                continue

        # All providers exhausted
        error_msg = f"All LLM providers failed. Last error: {last_error}"
        logger.error(f"extract_edital_data: ✗ {error_msg}")
        raise RuntimeError(error_msg)
