"""
Application settings via pydantic-settings.
Reads values from environment variables or .env file.

All components import `settings` from here — never read env vars directly.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Neo4j AuraDB
    neo4j_uri: str = Field(default="bolt://localhost:7687")
    neo4j_user: str = Field(default="neo4j")
    neo4j_password: str = Field(default="password")

    # Claude API
    anthropic_api_key: str = Field(default="")
    agent_llm_model: str = Field(default="claude-sonnet-4-5")
    agent_llm_max_tokens: int = Field(default=2048)

    # App
    app_env: str = Field(default="development")
    cors_origins: str = Field(default="http://localhost:5173")
    log_level: str = Field(default="INFO")

    # Ingestion
    gtf_data_dir: str = Field(default="./data/gtf")
    biomart_data_dir: str = Field(default="./data/biomart")
    ingest_batch_size: int = Field(default=1000)
    neighborhood_window_bp: int = Field(default=10000)

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


settings = Settings()
