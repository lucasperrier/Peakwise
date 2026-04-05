from __future__ import annotations

from peakwise.config import Settings


def test_default_settings():
    settings = Settings(database_url="sqlite:///:memory:", openai_api_key="test-key")
    assert settings.database_url == "sqlite:///:memory:"
    assert settings.debug is False
