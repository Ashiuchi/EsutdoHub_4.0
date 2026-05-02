import logging
from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import Any, Optional


logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    gemini_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    nvidia_api_key: Optional[str] = None

    # Clerk Auth
    clerk_secret_key: Optional[str] = None
    clerk_jwt_issuer: Optional[str] = None

    admin_user_ids: str = ""

    database_url: str = "sqlite:///./dev.db"
    debug: bool = False
    use_local_llm: bool = True
    ollama_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2:1b"
    ollama_model_cheap: str = "llama3.2:1b"
    ollama_timeout: int = 600
    gemini_timeout: int = 15
    groq_timeout: int = 30
    openrouter_timeout: int = 45
    nvidia_timeout: int = 60

    llm_strategy: str = "local_first"
    cloud_fallback: bool = True
    allowed_origins: Any = ["http://localhost:3000"]

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


settings = Settings()
logger.info("✅ Settings loaded from environment variables (Vault bypassed)")
