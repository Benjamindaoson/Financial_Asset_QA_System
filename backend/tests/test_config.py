"""Tests for application settings."""

import os
from unittest.mock import patch

import pytest

from app.config import Settings


class TestSettings:
    def test_settings_with_env_vars(self):
        env_vars = {
            "DEEPSEEK_API_KEY": "test_deepseek_key",
            "DEEPSEEK_BASE_URL": "https://api.test.com",
            "DEEPSEEK_MODEL": "deepseek-chat",
            "REDIS_HOST": "localhost",
            "REDIS_PORT": "6379",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings(_env_file=None)

        assert settings.DEEPSEEK_API_KEY == "test_deepseek_key"
        assert settings.DEEPSEEK_BASE_URL == "https://api.test.com"
        assert settings.DEEPSEEK_MODEL == "deepseek-chat"
        assert settings.REDIS_PORT == 6379

    def test_settings_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(_env_file=None)

        assert settings.DEEPSEEK_API_KEY == ""
        assert settings.DEEPSEEK_BASE_URL == "https://api.deepseek.com"
        assert settings.DEEPSEEK_MODEL == "deepseek-chat"
        assert settings.CACHE_TTL_PRICE == 60
        assert settings.LOG_LEVEL == "INFO"

    def test_optional_fields(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(_env_file=None)

        assert settings.TAVILY_API_KEY is None
        assert settings.ALPHA_VANTAGE_API_KEY is None

    def test_cache_settings(self):
        env_vars = {
            "CACHE_TTL_PRICE": "120",
            "CACHE_TTL_HISTORY": "172800",
            "CACHE_WARM_ENABLED": "true",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings(_env_file=None)

        assert settings.CACHE_TTL_PRICE == 120
        assert settings.CACHE_TTL_HISTORY == 172800
        assert settings.CACHE_WARM_ENABLED is True

    def test_model_settings(self):
        env_vars = {
            "EMBEDDING_MODEL": "BAAI/bge-large-zh-v1.5",
            "RERANKER_MODEL": "BAAI/bge-reranker-large",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings(_env_file=None)

        assert settings.EMBEDDING_MODEL == "BAAI/bge-large-zh-v1.5"
        assert settings.RERANKER_MODEL == "BAAI/bge-reranker-large"


class TestSettingsValidation:
    def test_invalid_port_number(self):
        with patch.dict(os.environ, {"REDIS_PORT": "invalid"}, clear=True):
            with pytest.raises(Exception):
                Settings(_env_file=None)

    def test_invalid_float_value(self):
        with patch.dict(os.environ, {"RAG_SCORE_THRESHOLD": "invalid"}, clear=True):
            with pytest.raises(Exception):
                Settings(_env_file=None)
