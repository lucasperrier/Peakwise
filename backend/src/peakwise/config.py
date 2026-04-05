from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://peakwise:peakwise@localhost:5432/peakwise"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    debug: bool = False

    model_config = {"env_prefix": "PEAKWISE_", "env_file": ".env"}
