import hvac
import os
from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    vault_addr: Optional[str] = None
    vault_token: Optional[str] = None
    
    gemini_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    nvidia_api_key: Optional[str] = None

    database_url: str = "sqlite:///./dev.db"
    debug: bool = False
    use_local_llm: bool = True
    ollama_url: str = "http://ollama:11434"
    ollama_timeout: int = 600
    gemini_timeout: int = 15
    groq_timeout: int = 30
    openrouter_timeout: int = 45
    nvidia_timeout: int = 60

    llm_strategy: str = "local_first"
    cloud_fallback: bool = True
    allowed_origins: List[str] = ["http://localhost:3000"]

    def __init__(self, **values):
        super().__init__(**values)
        # Try to load secrets from Vault if configured
        if self.vault_addr and self.vault_token:
            try:
                client = hvac.Client(url=self.vault_addr, token=self.vault_token)
                if client.is_authenticated():
                    read_response = client.secrets.kv.v2.read_secret_version(
                        path="estudohub",
                        mount_point="secret"
                    )
                    vault_secrets = read_response["data"]["data"]
                    
                    # Override with Vault secrets if they exist
                    if "GEMINI_API_KEY" in vault_secrets:
                        self.gemini_api_key = vault_secrets["GEMINI_API_KEY"]
                    if "GROQ_API_KEY" in vault_secrets:
                        self.groq_api_key = vault_secrets["GROQ_API_KEY"]
                    if "OPENROUTER_API_KEY" in vault_secrets:
                        self.openrouter_api_key = vault_secrets["OPENROUTER_API_KEY"]
                    if "NVIDIA_API_KEY" in vault_secrets:
                        self.nvidia_api_key = vault_secrets["NVIDIA_API_KEY"]
                    if "DATABASE_URL" in vault_secrets:
                        self.database_url = vault_secrets["DATABASE_URL"]
                    
                    print(f"Successfully loaded secrets from Vault at {self.vault_addr}")
                else:
                    print("Vault authentication failed.")
            except Exception as e:
                print(f"Could not connect to Vault, using environment variables: {e}")

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
