"""Tests for PromptManager."""

import pytest
from pathlib import Path
from app.core.prompt_manager import PromptManager


def test_prompt_manager_loads_yaml():
    """Test that PromptManager can load prompts.yaml."""
    manager = PromptManager()

    # Should load without errors
    assert manager is not None


def test_get_system_prompt():
    """Test getting system prompt for router."""
    manager = PromptManager()

    system_prompt = manager.get_system_prompt("router")

    assert system_prompt is not None
    assert isinstance(system_prompt, str)
    assert len(system_prompt) > 0
    assert "金融问题分类器" in system_prompt


def test_render_user_prompt():
    """Test rendering user prompt with variables."""
    manager = PromptManager()

    rendered = manager.render_user_prompt(
        "router",
        user_question="AAPL今天涨了多少？"
    )

    assert rendered is not None
    assert "AAPL今天涨了多少？" in rendered


def test_get_temperature():
    """Test getting temperature config for different prompt types."""
    manager = PromptManager()

    router_temp = manager.get_temperature("router")
    generator_temp = manager.get_temperature("generator")
    compliance_temp = manager.get_temperature("compliance")

    assert router_temp == 0.0
    assert generator_temp == 0.3
    assert compliance_temp == 0.0


def test_get_max_tokens():
    """Test getting max_tokens config."""
    manager = PromptManager()

    router_tokens = manager.get_max_tokens("router")
    generator_tokens = manager.get_max_tokens("generator")

    assert router_tokens == 500
    assert generator_tokens == 2000


def test_get_config():
    """Test getting hybrid routing config."""
    manager = PromptManager()

    config = manager.get_config("hybrid_routing")

    assert config is not None
    assert config["enabled"] is True
    assert config["confidence_threshold"] == 0.8
    assert config["fallback_to_rule"] is True


def test_invalid_prompt_type():
    """Test handling of invalid prompt type."""
    manager = PromptManager()

    with pytest.raises(KeyError):
        manager.get_system_prompt("invalid_type")
