import os
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "EDUCORE AI - PS2"
    PROJECT_DESCRIPTION: str = "Automated Formative Assessment and Intelligent Subjective Grading Assistant"
    API_PREFIX: str = "/api/ps2"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000"

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_STORAGE_BUCKET: str = "ps2-submissions"

    # AI / LLM & Semantic Matching Engine
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    DEFAULT_EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    SEMANTIC_SIMILARITY_THRESHOLD: float = 0.55
    HIGH_CONFIDENCE_THRESHOLD: float = 0.75
    EVIDENCE_MATCH_THRESHOLD: float = 0.50
    ENABLE_NEURAL_EMBEDDINGS: bool = True

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()

