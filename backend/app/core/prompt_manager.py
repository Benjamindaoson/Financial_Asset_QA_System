"""Prompt management using prompts.yaml."""

from pathlib import Path
from typing import Any, Dict

import yaml
from jinja2 import Template

from app.config import settings


class PromptManager:
    """Manages loading and rendering of prompts from prompts.yaml."""

    def __init__(self, config_path: str = None):
        """Initialize PromptManager.

        Args:
            config_path: Path to prompts.yaml file. If None, uses settings.PROMPTS_CONFIG_PATH
        """
        if config_path is None:
            # Look for prompts.yaml in project root
            # __file__ is in backend/app/core/prompt_manager.py
            # Project root is 3 levels up: backend/app/core -> backend/app -> backend -> root
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            config_path = project_root / settings.PROMPTS_CONFIG_PATH

        self.config_path = Path(config_path).resolve()
        self._data = self._load_yaml()

    def _load_yaml(self) -> Dict[str, Any]:
        """Load and parse prompts.yaml file.

        Returns:
            Parsed YAML data as dictionary

        Raises:
            FileNotFoundError: If prompts.yaml not found
            yaml.YAMLError: If YAML parsing fails
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Prompts config not found: {self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def get_system_prompt(self, prompt_type: str) -> str:
        """Get system prompt for a given prompt type.

        Args:
            prompt_type: Type of prompt (router, generator, compliance)

        Returns:
            System prompt string

        Raises:
            KeyError: If prompt_type not found
        """
        return self._data["prompts"][prompt_type]["system_prompt"]

    def render_user_prompt(self, prompt_type: str, **kwargs) -> str:
        """Render user prompt template with variables.

        Args:
            prompt_type: Type of prompt (router, generator, compliance)
            **kwargs: Variables to substitute in template

        Returns:
            Rendered prompt string

        Raises:
            KeyError: If prompt_type not found
        """
        template_str = self._data["prompts"][prompt_type]["user_template"]
        template = Template(template_str)
        return template.render(**kwargs)

    def get_temperature(self, prompt_type: str) -> float:
        """Get temperature setting for a prompt type.

        Args:
            prompt_type: Type of prompt (router, generator, compliance)

        Returns:
            Temperature value
        """
        return self._data["config"]["temperature"][prompt_type]

    def get_max_tokens(self, prompt_type: str) -> int:
        """Get max_tokens setting for a prompt type.

        Args:
            prompt_type: Type of prompt (router, generator, compliance)

        Returns:
            Max tokens value
        """
        return self._data["config"]["max_tokens"][prompt_type]

    def get_config(self, config_key: str) -> Any:
        """Get configuration value by key.

        Args:
            config_key: Configuration key (e.g., 'hybrid_routing')

        Returns:
            Configuration value

        Raises:
            KeyError: If config_key not found
        """
        return self._data["config"][config_key]

    def reload(self) -> None:
        """Reload prompts.yaml from disk.

        Useful for hot-reloading configuration changes.
        """
        self._data = self._load_yaml()
