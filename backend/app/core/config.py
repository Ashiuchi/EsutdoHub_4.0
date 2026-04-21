from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    gemini_api_key: Optional[str] = None
    debug: bool = False
    use_local_llm: bool = True
    ollama_url: str = "http://host.docker.internal:11434"
    ollama_timeout: int = 120
    gemini_timeout: int = 15
    llm_strategy: str = "local_first"
    cloud_fallback: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

settings = Settings()
