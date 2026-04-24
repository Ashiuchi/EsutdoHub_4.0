from .openai_compatible_provider import OpenAICompatibleProvider
from app.core.config import settings

class NVIDIAProvider(OpenAICompatibleProvider):
    def __init__(self, api_key: str = None, model: str = "meta/llama-3.1-405b-instruct", timeout: int = None):
        super().__init__(
            name="NVIDIA",
            api_key=api_key or settings.nvidia_api_key,
            base_url="https://integrate.api.nvidia.com/v1",
            model=model,
            timeout=timeout or settings.nvidia_timeout
        )
