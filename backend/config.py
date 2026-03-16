"""Configuration management using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/ai_kanban"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Obsidian
    obsidian_vault_path: str = "/home/mwu/Work/notes/Work/TODO.md"

    # AI
    anthropic_api_key: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Feature flags
    enable_ai: bool = True
    enable_sync: bool = True


settings = Settings()
