"""
测试配置管理
"""
import pytest
import os
from unittest.mock import patch
from app.config import Settings


class TestSettings:
    """测试Settings配置类"""

    def test_settings_with_env_vars(self):
        """测试使用环境变量的配置"""
        env_vars = {
            'ANTHROPIC_API_KEY': 'test_anthropic_key',
            'ANTHROPIC_BASE_URL': 'https://api.test.com',
            'DEEPSEEK_API_KEY': 'test_deepseek_key',
            'REDIS_HOST': 'localhost',
            'REDIS_PORT': '6379',
            'CLAUDE_MODEL': 'claude-opus-4-6'
        }

        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()

            assert settings.ANTHROPIC_API_KEY == 'test_anthropic_key'
            assert settings.ANTHROPIC_BASE_URL == 'https://api.test.com'
            assert settings.DEEPSEEK_API_KEY == 'test_deepseek_key'
            assert settings.REDIS_HOST == 'localhost'
            assert settings.REDIS_PORT == 6379
            assert settings.CLAUDE_MODEL == 'claude-opus-4-6'

    def test_settings_defaults(self):
        """测试默认配置值"""
        env_vars = {
            'ANTHROPIC_API_KEY': 'test_key'
        }

        with patch.dict(os.environ, env_vars, clear=True):
            # 清除.env文件的影响
            with patch('app.config.Settings.Config.env_file', None):
                settings = Settings(_env_file=None)

                # 测试默认值
                assert settings.REDIS_HOST == 'localhost'
                assert settings.REDIS_PORT == 6379
                assert settings.REDIS_DB == 0
                assert settings.CLAUDE_MODEL == 'claude-sonnet-4-6'
                assert settings.CACHE_TTL_PRICE == 60
                assert settings.CACHE_TTL_HISTORY == 86400
                assert settings.LOG_LEVEL == 'INFO'

    def test_settings_optional_fields(self):
        """测试可选配置字段"""
        env_vars = {
            'ANTHROPIC_API_KEY': 'test_key'
        }

        with patch.dict(os.environ, env_vars, clear=True):
            # 清除.env文件的影响
            with patch('app.config.Settings.Config.env_file', None):
                settings = Settings(_env_file=None)

                # 可选字段应该是None（如果没有在环境变量中设置）
                assert settings.TAVILY_API_KEY is None
                assert settings.ALPHA_VANTAGE_API_KEY is None

    def test_settings_cache_ttl(self):
        """测试缓存TTL配置"""
        env_vars = {
            'ANTHROPIC_API_KEY': 'test_key',
            'CACHE_TTL_PRICE': '120',
            'CACHE_TTL_HISTORY': '172800',
            'CACHE_TTL_INFO': '1209600'
        }

        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()

            assert settings.CACHE_TTL_PRICE == 120
            assert settings.CACHE_TTL_HISTORY == 172800
            assert settings.CACHE_TTL_INFO == 1209600

    def test_settings_rag_config(self):
        """测试RAG配置"""
        env_vars = {
            'ANTHROPIC_API_KEY': 'test_key',
            'RAG_TOP_K': '20',
            'RAG_TOP_N': '5',
            'RAG_SCORE_THRESHOLD': '0.8'
        }

        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()

            assert settings.RAG_TOP_K == 20
            assert settings.RAG_TOP_N == 5
            assert settings.RAG_SCORE_THRESHOLD == 0.8

    def test_settings_model_config(self):
        """测试模型配置"""
        env_vars = {
            'ANTHROPIC_API_KEY': 'test_key',
            'CLAUDE_MODEL': 'claude-opus-4-6',
            'EMBEDDING_MODEL': 'BAAI/bge-large-zh-v1.5',
            'RERANKER_MODEL': 'BAAI/bge-reranker-large'
        }

        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()

            assert settings.CLAUDE_MODEL == 'claude-opus-4-6'
            assert settings.EMBEDDING_MODEL == 'BAAI/bge-large-zh-v1.5'
            assert settings.RERANKER_MODEL == 'BAAI/bge-reranker-large'

    def test_settings_api_config(self):
        """测试API配置"""
        env_vars = {
            'ANTHROPIC_API_KEY': 'test_key',
            'API_TIMEOUT': '60',
            'MAX_RETRIES': '5'
        }

        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()

            assert settings.API_TIMEOUT == 60
            assert settings.MAX_RETRIES == 5

    def test_settings_logging_config(self):
        """测试日志配置"""
        env_vars = {
            'ANTHROPIC_API_KEY': 'test_key',
            'LOG_LEVEL': 'DEBUG',
            'LOG_FILE': '../logs/custom.jsonl'
        }

        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()

            assert settings.LOG_LEVEL == 'DEBUG'
            assert settings.LOG_FILE == '../logs/custom.jsonl'

    def test_settings_redis_config(self):
        """测试Redis配置"""
        env_vars = {
            'ANTHROPIC_API_KEY': 'test_key',
            'REDIS_HOST': 'redis.example.com',
            'REDIS_PORT': '6380',
            'REDIS_DB': '1'
        }

        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()

            assert settings.REDIS_HOST == 'redis.example.com'
            assert settings.REDIS_PORT == 6380
            assert settings.REDIS_DB == 1

    def test_settings_chroma_config(self):
        """测试ChromaDB配置"""
        env_vars = {
            'ANTHROPIC_API_KEY': 'test_key',
            'CHROMA_PERSIST_DIR': '../custom_vectorstore/chroma'
        }

        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()

            assert settings.CHROMA_PERSIST_DIR == '../custom_vectorstore/chroma'

    def test_settings_huggingface_cache(self):
        """测试HuggingFace缓存配置"""
        env_vars = {
            'ANTHROPIC_API_KEY': 'test_key',
            'HF_HOME': '../custom_models/huggingface',
            'TRANSFORMERS_CACHE': '../custom_models/transformers'
        }

        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()

            assert settings.HF_HOME == '../custom_models/huggingface'
            assert settings.TRANSFORMERS_CACHE == '../custom_models/transformers'

    def test_settings_multi_model_keys(self):
        """测试多模型API密钥配置"""
        env_vars = {
            'ANTHROPIC_API_KEY': 'anthropic_key',
            'DEEPSEEK_API_KEY': 'deepseek_key',
            'OPENAI_API_KEY': 'openai_key'
        }

        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()

            assert settings.ANTHROPIC_API_KEY == 'anthropic_key'
            assert settings.DEEPSEEK_API_KEY == 'deepseek_key'
            assert settings.OPENAI_API_KEY == 'openai_key'


class TestSettingsValidation:
    """测试配置验证"""

    def test_missing_required_field(self):
        """测试缺少必需字段"""
        with patch.dict(os.environ, {}, clear=True):
            # 清除.env文件的影响
            with patch('app.config.Settings.Config.env_file', None):
                with pytest.raises(Exception):
                    # ANTHROPIC_API_KEY是必需的
                    Settings(_env_file=None)

    def test_invalid_port_number(self):
        """测试无效的端口号"""
        env_vars = {
            'ANTHROPIC_API_KEY': 'test_key',
            'REDIS_PORT': 'invalid'
        }

        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(Exception):
                Settings()

    def test_invalid_float_value(self):
        """测试无效的浮点数值"""
        env_vars = {
            'ANTHROPIC_API_KEY': 'test_key',
            'RAG_SCORE_THRESHOLD': 'invalid'
        }

        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(Exception):
                Settings()
