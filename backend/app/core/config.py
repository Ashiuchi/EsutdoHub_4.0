from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    gemini_api_key: Optional[str] = None
    debug: bool = False
    use_local_llm: bool = True
    ollama_url: str = "http://host.docker.internal:11434"
    ollama_timeout: int = 600
    gemini_timeout: int = 15
    llm_strategy: str = "local_first"
    cloud_fallback: bool = True
    allowed_origins: List[str] = ["http://localhost:3000"]

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


settings = Settings()
