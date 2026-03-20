"""Tool plugin system for extensibility."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import importlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ToolPlugin(ABC):
    """Base class for tool plugins.

    All custom tools should inherit from this class and implement
    the required methods. This allows dynamic tool loading without
    modifying core code.

    Example:
        class CryptoToolPlugin(ToolPlugin):
            @property
            def name(self) -> str:
                return "get_crypto_price"

            @property
            def description(self) -> str:
                return "Get cryptocurrency price from Binance"

            @property
            def input_schema(self) -> Dict[str, Any]:
                return {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"}
                    },
                    "required": ["symbol"]
                }

            async def execute(self, **kwargs) -> Dict[str, Any]:
                symbol = kwargs["symbol"]
                # Call Binance API
                return {"price": 50000, "source": "binance"}
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name (must be unique)."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description for LLM routing."""
        pass

    @property
    @abstractmethod
    def input_schema(self) -> Dict[str, Any]:
        """JSON schema for input parameters."""
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool with given parameters.

        Args:
            **kwargs: Tool parameters matching input_schema

        Returns:
            Tool execution result as dictionary

        Raises:
            Exception: If tool execution fails
        """
        pass

    def to_tool_definition(self) -> Dict[str, Any]:
        """Convert plugin to tool definition format.

        Returns:
            Tool definition compatible with AgentCore
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema
        }


class PluginRegistry:
    """Registry for managing tool plugins.

    This registry allows dynamic discovery and registration of tool plugins.
    Plugins can be loaded from a directory or registered programmatically.

    Usage:
        registry = PluginRegistry()
        registry.discover_plugins("plugins/")

        # Get all registered tools
        tools = registry.get_all_tools()

        # Execute a tool
        result = await registry.execute("get_crypto_price", symbol="BTC")
    """

    def __init__(self):
        self.plugins: Dict[str, ToolPlugin] = {}
        logger.info("[PluginRegistry] Initialized")

    def register(self, plugin: ToolPlugin):
        """Register a plugin instance.

        Args:
            plugin: ToolPlugin instance to register

        Raises:
            ValueError: If plugin name already registered
        """
        if plugin.name in self.plugins:
            logger.warning(
                f"[PluginRegistry] Plugin '{plugin.name}' already registered, "
                "overwriting"
            )

        self.plugins[plugin.name] = plugin
        logger.info(f"[PluginRegistry] Registered plugin: {plugin.name}")

    def unregister(self, name: str):
        """Unregister a plugin by name.

        Args:
            name: Plugin name to unregister
        """
        if name in self.plugins:
            del self.plugins[name]
            logger.info(f"[PluginRegistry] Unregistered plugin: {name}")

    def discover_plugins(self, plugin_dir: str = "plugins/"):
        """Automatically discover and load plugins from directory.

        Scans the plugin directory for Python files and attempts to
        load any ToolPlugin subclasses found.

        Args:
            plugin_dir: Directory path to scan for plugins
        """
        plugin_path = Path(plugin_dir)

        if not plugin_path.exists():
            logger.warning(
                f"[PluginRegistry] Plugin directory not found: {plugin_dir}"
            )
            return

        logger.info(f"[PluginRegistry] Discovering plugins in {plugin_dir}")

        for file in plugin_path.glob("*.py"):
            if file.stem.startswith("_"):
                continue  # Skip __init__.py and private files

            try:
                # Import module
                module_name = f"plugins.{file.stem}"
                module = importlib.import_module(module_name)

                # Find ToolPlugin subclasses
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)

                    # Check if it's a ToolPlugin subclass (but not ToolPlugin itself)
                    if (isinstance(attr, type) and
                        issubclass(attr, ToolPlugin) and
                        attr is not ToolPlugin):

                        # Instantiate and register
                        plugin_instance = attr()
                        self.register(plugin_instance)

            except Exception as e:
                logger.error(
                    f"[PluginRegistry] Failed to load plugin from {file}: {e}"
                )

    def get_plugin(self, name: str) -> Optional[ToolPlugin]:
        """Get plugin by name.

        Args:
            name: Plugin name

        Returns:
            ToolPlugin instance or None if not found
        """
        return self.plugins.get(name)

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """Get all registered tools as tool definitions.

        Returns:
            List of tool definitions compatible with AgentCore
        """
        return [plugin.to_tool_definition() for plugin in self.plugins.values()]

    async def execute(self, name: str, **kwargs) -> Dict[str, Any]:
        """Execute a plugin by name.

        Args:
            name: Plugin name
            **kwargs: Plugin parameters

        Returns:
            Plugin execution result

        Raises:
            ValueError: If plugin not found
            Exception: If plugin execution fails
        """
        plugin = self.get_plugin(name)

        if plugin is None:
            raise ValueError(f"Plugin not found: {name}")

        logger.info(f"[PluginRegistry] Executing plugin: {name}")
        result = await plugin.execute(**kwargs)

        return result

    def list_plugins(self) -> List[str]:
        """List all registered plugin names.

        Returns:
            List of plugin names
        """
        return list(self.plugins.keys())


# Global registry instance
plugin_registry = PluginRegistry()
