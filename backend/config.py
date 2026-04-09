"""Configuration management using pydantic-settings."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    yaml = None


def _load_config_yaml(path: str) -> dict[str, object]:
    """Load config.yaml with full YAML support when available."""
    p = Path(path)
    if not p.exists():
        return {}

    content = p.read_text(encoding="utf-8")
    if yaml is None:
        raise RuntimeError(
            "PyYAML is required to parse config.yaml with project settings."
        )

    data = yaml.safe_load(content) or {}
    if not isinstance(data, dict):
        return {}
    return data


class ContextItem(BaseModel):
    type: Literal["repo", "url", "path"]
    value: str


class YouTrackConfig(BaseModel):
    url: str = ""
    token_env: str = "YOUTRACK_TOKEN"
    project_key: str = ""
    query: str = ""
    poll_seconds: int = 600

    def resolve_token(self) -> str:
        return os.environ.get(self.token_env, "")


class ProjectConfig(BaseModel):
    name: str
    kanban_path: str
    context: list[ContextItem] = []
    youtrack: YouTrackConfig = Field(default_factory=YouTrackConfig)

    def resolve_kanban_path(self, vault_root: str) -> Path:
        path = Path(self.kanban_path).expanduser()
        if not path.is_absolute() and vault_root:
            path = Path(vault_root).expanduser() / path
        return path


def _apply_config_yaml(settings: "Settings") -> None:
    """Apply config.yaml values when env vars are not set."""
    data = _load_config_yaml("config.yaml")
    if not data:
        return

    def _env_set(name: str) -> bool:
        return name.upper() in os.environ

    if "obsidian_vault_path" in data and not _env_set("OBSIDIAN_VAULT_PATH"):
        settings.obsidian_vault_path = str(data["obsidian_vault_path"])

    if "obsidian_vault_root" in data and not _env_set("OBSIDIAN_VAULT_ROOT"):
        settings.obsidian_vault_root = str(data["obsidian_vault_root"])

    if "projects" in data and not _env_set("PROJECTS"):
        raw = data["projects"]
        if isinstance(raw, list):
            try:
                settings.projects = [ProjectConfig.model_validate(item) for item in raw]
            except ValidationError as exc:
                raise ValueError(f"Invalid projects config: {exc}") from exc

    if "obsidian_vault_host_path" in data and not _env_set("OBSIDIAN_VAULT_HOST_PATH"):
        settings.obsidian_vault_host_path = str(data["obsidian_vault_host_path"])

    if "obsidian_vault_container_path" in data and not _env_set(
        "OBSIDIAN_VAULT_CONTAINER_PATH"
    ):
        settings.obsidian_vault_container_path = str(
            data["obsidian_vault_container_path"]
        )

    if settings.projects and not _env_set("OBSIDIAN_VAULT_PATH"):
        default_project = settings.projects[0]
        settings.obsidian_vault_path = str(
            default_project.resolve_kanban_path(settings.obsidian_vault_root)
        )
class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/ai_kanban"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Obsidian
    obsidian_vault_path: str = "/home/mwu/Work/notes/Work/TODO.md"
    obsidian_vault_root: str = ""
    obsidian_vault_host_path: str = ""
    obsidian_vault_container_path: str = ""
    projects: list[ProjectConfig] = []

    # AI
    anthropic_api_key: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Feature flags
    enable_ai: bool = True
    enable_sync: bool = True


settings = Settings()
_apply_config_yaml(settings)
