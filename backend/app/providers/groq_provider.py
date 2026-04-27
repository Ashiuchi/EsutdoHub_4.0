from .openai_compatible_provider import OpenAICompatibleProvider
from app.core.config import settings

class GroqProvider(OpenAICompatibleProvider):
    def __init__(self, api_key: str = None, model: str = "llama-3.3-70b-versatile", timeout: int = None):
        super().__init__(
            name="Groq",
            api_key=api_key or settings.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
            model=model,
            timeout=timeout or settings.groq_timeout
        )
