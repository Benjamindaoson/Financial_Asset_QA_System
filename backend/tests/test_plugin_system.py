"""Test plugin system."""

import pytest
from app.plugins.base import ToolPlugin, PluginRegistry


class MockPlugin(ToolPlugin):
    """Mock plugin for testing."""

    @property
    def name(self) -> str:
        return "mock_tool"

    @property
    def description(self) -> str:
        return "A mock tool for testing"

    @property
    def input_schema(self):
        return {
            "type": "object",
            "properties": {
                "param1": {"type": "string"}
            },
            "required": ["param1"]
        }

    async def execute(self, **kwargs):
        return {"result": f"Executed with {kwargs.get('param1')}"}


class TestPluginSystem:
    """Test suite for plugin system."""

    @pytest.fixture
    def registry(self):
        """Create fresh plugin registry."""
        return PluginRegistry()

    @pytest.fixture
    def mock_plugin(self):
        """Create mock plugin instance."""
        return MockPlugin()

    def test_plugin_registration(self, registry, mock_plugin):
        """Test plugin registration."""
        registry.register(mock_plugin)

        assert "mock_tool" in registry.list_plugins()
        assert registry.get_plugin("mock_tool") is not None

    def test_plugin_unregistration(self, registry, mock_plugin):
        """Test plugin unregistration."""
        registry.register(mock_plugin)
        assert "mock_tool" in registry.list_plugins()

        registry.unregister("mock_tool")
        assert "mock_tool" not in registry.list_plugins()

    def test_get_all_tools(self, registry, mock_plugin):
        """Test getting all tool definitions."""
        registry.register(mock_plugin)

        tools = registry.get_all_tools()

        assert len(tools) == 1
        assert tools[0]["name"] == "mock_tool"
        assert tools[0]["description"] == "A mock tool for testing"
        assert "input_schema" in tools[0]

    @pytest.mark.asyncio
    async def test_plugin_execution(self, registry, mock_plugin):
        """Test plugin execution."""
        registry.register(mock_plugin)

        result = await registry.execute("mock_tool", param1="test_value")

        assert result["result"] == "Executed with test_value"

    @pytest.mark.asyncio
    async def test_plugin_not_found(self, registry):
        """Test executing non-existent plugin."""
        with pytest.raises(ValueError, match="Plugin not found"):
            await registry.execute("nonexistent_tool")

    def test_plugin_to_tool_definition(self, mock_plugin):
        """Test converting plugin to tool definition."""
        definition = mock_plugin.to_tool_definition()

        assert definition["name"] == "mock_tool"
        assert definition["description"] == "A mock tool for testing"
        assert definition["input_schema"]["type"] == "object"

    def test_duplicate_registration_warning(self, registry, mock_plugin, caplog):
        """Test warning on duplicate registration."""
        registry.register(mock_plugin)
        registry.register(mock_plugin)  # Register again

        # Should log warning but still work
        assert "already registered" in caplog.text.lower()
        assert "mock_tool" in registry.list_plugins()
