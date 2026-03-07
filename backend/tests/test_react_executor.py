"""Tests for ReAct executor."""
import pytest
from app.agent.react_executor import ReActExecutor, ReActStep


def test_react_step_initialization():
    """Test ReActStep initialization."""
    step = ReActStep(
        thought="I need to get the price",
        action="get_price",
        action_input={"symbol": "AAPL"},
        observation='{"price": 150.0}'
    )

    assert step.thought == "I need to get the price"
    assert step.action == "get_price"
    assert step.action_input == {"symbol": "AAPL"}
    assert step.observation == '{"price": 150.0}'
    assert step.timestamp is not None


def test_react_executor_initialization():
    """Test ReActExecutor initialization."""
    tools = [
        {
            "name": "get_price",
            "description": "Get stock price",
            "input_schema": {"type": "object"}
        }
    ]

    executor = ReActExecutor(tools=tools, max_iterations=3)

    assert executor.tools == tools
    assert executor.max_iterations == 3
    assert executor.steps == []


def test_build_react_prompt_no_steps():
    """Test building ReAct prompt with no previous steps."""
    tools = [
        {
            "name": "get_price",
            "description": "Get stock price",
            "input_schema": {}
        }
    ]

    executor = ReActExecutor(tools=tools)
    prompt = executor._build_react_prompt("What is AAPL price?", [])

    assert "What is AAPL price?" in prompt
    assert "get_price" in prompt
    assert "Thought:" in prompt
    assert "Action:" in prompt


def test_build_react_prompt_with_steps():
    """Test building ReAct prompt with previous steps."""
    tools = [{"name": "get_price", "description": "Get stock price", "input_schema": {}}]

    executor = ReActExecutor(tools=tools)
    steps = [
        ReActStep(
            thought="I need the price",
            action="get_price",
            action_input={"symbol": "AAPL"},
            observation='{"price": 150.0}'
        )
    ]

    prompt = executor._build_react_prompt("What is AAPL price?", steps)

    assert "Previous steps:" in prompt
    assert "I need the price" in prompt
    assert "get_price" in prompt
    assert '{"price": 150.0}' in prompt


def test_parse_react_response_simple():
    """Test parsing simple ReAct response."""
    executor = ReActExecutor(tools=[])

    response = """Thought: I need to get the stock price
Action: get_price
Action Input: {"symbol": "AAPL"}"""

    parsed = executor._parse_react_response(response)

    assert parsed["thought"] == "I need to get the stock price"
    assert parsed["action"] == "get_price"
    assert parsed["action_input"] == {"symbol": "AAPL"}


def test_parse_react_response_final_answer():
    """Test parsing ReAct response with final answer."""
    executor = ReActExecutor(tools=[])

    response = """Thought: I have enough information to answer
Action: Final Answer
Action Input: The price of AAPL is $150.00"""

    parsed = executor._parse_react_response(response)

    assert parsed["thought"] == "I have enough information to answer"
    assert "final answer" in parsed["action"].lower()
    assert "150.00" in parsed["action_input"]["query"]


def test_parse_react_response_multiline():
    """Test parsing multiline ReAct response."""
    executor = ReActExecutor(tools=[])

    response = """Thought: I need to analyze the stock
This requires multiple steps
Action: get_price
Action Input: {"symbol": "AAPL"}"""

    parsed = executor._parse_react_response(response)

    assert "multiple steps" in parsed["thought"]
    assert parsed["action"] == "get_price"


@pytest.mark.asyncio
async def test_execute_react_loop():
    """Test executing ReAct loop."""
    tools = [{"name": "get_price", "description": "Get price", "input_schema": {}}]
    executor = ReActExecutor(tools=tools, max_iterations=2)

    call_count = 0

    async def mock_llm_generate(prompt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return """Thought: I need to get the price
Action: get_price
Action Input: {"symbol": "AAPL"}"""
        else:
            return """Thought: I have the price now
Action: Final Answer
Action Input: The price is $150.00"""

    async def mock_tool_execute(action, action_input):
        return {"price": 150.0, "symbol": "AAPL"}

    events = []
    async for event in executor.execute("What is AAPL price?", mock_llm_generate, mock_tool_execute):
        events.append(event)

    # Check we got expected events
    event_types = [e.type for e in events]
    assert "react_iteration" in event_types
    assert "react_thought" in event_types
    assert "react_action" in event_types
    assert "react_observation" in event_types
    assert "react_final_answer" in event_types
    assert "react_complete" in event_types
