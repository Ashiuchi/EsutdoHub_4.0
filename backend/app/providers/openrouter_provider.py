from .openai_compatible_provider import OpenAICompatibleProvider
from app.core.config import settings

class OpenRouterProvider(OpenAICompatibleProvider):
    def __init__(self, api_key: str = None, model: str = "openrouter/auto", timeout: int = None):
        super().__init__(
            name="OpenRouter",
            api_key=api_key or settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
            model=model,
            timeout=timeout or settings.openrouter_timeout,
            extra_headers={
                "HTTP-Referer": "https://estudohub.pro", # Opcional, mas recomendado
                "X-Title": "EstudoHub Pro 4.0"
            }
        )
