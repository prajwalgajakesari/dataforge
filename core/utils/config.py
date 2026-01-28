"""
Configuration management for DataForge.

Loads configuration from environment variables and .env files.
"""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DataForgeSettings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Core Configuration
    dataforge_env: str = Field(default="development", alias="DATAFORGE_ENV")
    dataforge_log_level: str = Field(default="INFO", alias="DATAFORGE_LOG_LEVEL")
    dataforge_workspace_dir: str = Field(
        default="~/dataforge-workspaces",
        alias="DATAFORGE_WORKSPACE_DIR"
    )

    # AI/LLM Configuration
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    default_model: str = Field(
        default="claude-3-5-sonnet-20241022",
        alias="DEFAULT_MODEL"
    )
    model_temperature: float = Field(default=0.0, alias="MODEL_TEMPERATURE")
    model_max_tokens: int = Field(default=4096, alias="MODEL_MAX_TOKENS")

    # Database Configuration
    postgres_host: Optional[str] = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_user: Optional[str] = Field(default="postgres", alias="POSTGRES_USER")
    postgres_password: Optional[str] = Field(default="", alias="POSTGRES_PASSWORD")
    postgres_database: Optional[str] = Field(
        default="dataforge_metadata",
        alias="POSTGRES_DATABASE"
    )

    # API Server Configuration
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_workers: int = Field(default=4, alias="API_WORKERS")
    api_reload: bool = Field(default=True, alias="API_RELOAD")
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        alias="CORS_ORIGINS"
    )

    # Security
    api_secret_key: str = Field(
        default="change_this_in_production",
        alias="API_SECRET_KEY"
    )
    credential_encryption_key: str = Field(
        default="change_this_in_production",
        alias="CREDENTIAL_ENCRYPTION_KEY"
    )
    enable_pii_detection: bool = Field(default=True, alias="ENABLE_PII_DETECTION")
    enable_audit_logging: bool = Field(default=True, alias="ENABLE_AUDIT_LOGGING")

    # Feature Flags
    enable_web_interface: bool = Field(default=False, alias="ENABLE_WEB_INTERFACE")
    enable_vscode_extension: bool = Field(
        default=False,
        alias="ENABLE_VSCODE_EXTENSION"
    )
    enable_pipeline_generation: bool = Field(
        default=False,
        alias="ENABLE_PIPELINE_GENERATION"
    )
    enable_infrastructure_generation: bool = Field(
        default=False,
        alias="ENABLE_INFRASTRUCTURE_GENERATION"
    )

    # Git Configuration
    git_user_name: str = Field(default="DataForge Bot", alias="GIT_USER_NAME")
    git_user_email: str = Field(default="bot@dataforge.dev", alias="GIT_USER_EMAIL")
    github_token: Optional[str] = Field(default=None, alias="GITHUB_TOKEN")

    # Development
    debug: bool = Field(default=False, alias="DEBUG")
    enable_profiling: bool = Field(default=False, alias="ENABLE_PROFILING")
    test_database_url: str = Field(
        default="sqlite:///./test.db",
        alias="TEST_DATABASE_URL"
    )

    def get_workspace_path(self) -> Path:
        """Get the workspace directory path."""
        return Path(self.dataforge_workspace_dir).expanduser().resolve()

    def get_cors_origins_list(self) -> list[str]:
        """Get CORS origins as a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    def is_production(self) -> bool:
        """Check if running in production."""
        return self.dataforge_env.lower() == "production"

    def is_development(self) -> bool:
        """Check if running in development."""
        return self.dataforge_env.lower() == "development"


# Global settings instance
settings = DataForgeSettings()
