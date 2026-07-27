from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://aihub:aihub_secret@localhost:5432/aihub"
    litellm_base_url: str = "http://localhost:4000"
    litellm_api_key: str = "sk-rag-service-change-me"

    # Required for /rag/* and /prompts/* — clients send it as X-API-Key
    rag_service_api_key: str = ""

    embedding_model: str = "text-embedding-3-small"
    chat_model: str = "gemini/gemini-2.0-flash"
    embedding_dimensions: int = 1536

    chunk_size: int = 800
    chunk_overlap: int = 120
    top_k: int = 5

    upload_dir: str = "/data/uploads"
    cors_origins: str = "*"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
