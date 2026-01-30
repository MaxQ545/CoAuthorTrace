"""
Configuration settings for Coauthor Tracing System.
"""
import json
from pathlib import Path
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScopeConfig(BaseSettings):
    """Scope configuration for data crawling."""
    model_config = SettingsConfigDict(
        env_prefix="COAUTHOR_SCOPE__",
        env_file=".env",
        extra="ignore"
    )

    institution_ids: list[str] = Field(default=["I114922016"])
    concept_ids: list[str] = Field(default=[
        "C41008148",    # Computer Science
        "C154945302",   # Artificial Intelligence
        "C119857082",   # Machine Learning
    ])
    source_ids: list[str] = Field(default=[])
    from_date: str = "2020-01-01"

    @field_validator("institution_ids", "concept_ids", "source_ids", mode="before")
    @classmethod
    def parse_list(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [x.strip() for x in v.split(",") if x.strip()]
        return v


class DatabaseSettings(BaseSettings):
    """Database configuration."""
    model_config = SettingsConfigDict(
        env_prefix="COAUTHOR_DATABASE__",
        env_file=".env",
        extra="ignore"
    )

    sqlite_path: Path = Field(default=Path("data/coauthor.db"))
    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = False


class CrawlerSettings(BaseSettings):
    """Crawler configuration."""
    model_config = SettingsConfigDict(
        env_prefix="COAUTHOR_CRAWLER__",
        env_file=".env",
        extra="ignore"
    )

    openalex_email: Optional[str] = None
    rate_limit: float = 8.0
    batch_size: int = 200
    max_retries: int = 3


class AnalysisSettings(BaseSettings):
    """Analysis configuration."""
    model_config = SettingsConfigDict(
        env_prefix="COAUTHOR_ANALYSIS__",
        env_file=".env",
        extra="ignore"
    )

    time_decay_half_life_days: int = 730  # 2 years
    hidden_dim: int = 64
    output_dim: int = 32
    num_layers: int = 2
    learning_rate: float = 0.01
    epochs: int = 100


class APISettings(BaseSettings):
    """API configuration."""
    model_config = SettingsConfigDict(
        env_prefix="COAUTHOR_API__",
        env_file=".env",
        extra="ignore"
    )

    host: str = "0.0.0.0"
    port: int = 8000
    cache_ttl: int = 86400  # 24 hours
    default_top_k: int = 20


class SchedulerSettings(BaseSettings):
    """Scheduler configuration."""
    model_config = SettingsConfigDict(
        env_prefix="COAUTHOR_SCHEDULER__",
        env_file=".env",
        extra="ignore"
    )

    crawl_cron_hour: int = 2
    analysis_cron_day: str = "sun"
    analysis_cron_hour: int = 4


class Settings:
    """Main settings class combining all configurations."""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent.resolve()
        self.scope = ScopeConfig()
        self.database = DatabaseSettings()
        self.crawler = CrawlerSettings()
        self.analysis = AnalysisSettings()
        self.api = APISettings()
        self.scheduler = SchedulerSettings()


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings
