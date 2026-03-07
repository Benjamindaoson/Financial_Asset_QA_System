"""Tests for conversation history management."""
import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime
import json

from app.conversation.history import ConversationHistory


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis_mock = Mock()
    redis_mock.get = Mock(return_value=None)
    redis_mock.setex = Mock()
    redis_mock.delete = Mock()
    return redis_mock


@pytest.fixture
def conversation_history(mock_redis):
    """Create ConversationHistory instance with mock Redis."""
    return ConversationHistory(redis_client=mock_redis)


def test_initialization_with_redis_client(mock_redis):
    """Test initialization with provided Redis client."""
    history = ConversationHistory(redis_client=mock_redis)
    assert history.redis == mock_redis
    assert history.ttl == 86400


def test_get_key():
    """Test Redis key generation."""
    history = ConversationHistory(redis_client=Mock())
    key = history._get_key("test-session-123")
    assert key == "conversation:test-session-123"


def test_add_message_to_empty_history(conversation_history, mock_redis):
    """Test adding first message to empty history."""
    mock_redis.get.return_value = None

    conversation_history.add_message(
        session_id="session-1",
        role="user",
        content="What is PE ratio?"
    )

    # Verify setex was called
    assert mock_redis.setex.called
    call_args = mock_redis.setex.call_args

    # Check key
    assert call_args[0][0] == "conversation:session-1"

    # Check TTL
    assert call_args[0][1] == 86400

    # Check data structure
    data = json.loads(call_args[0][2])
    assert len(data) == 1
    assert data[0]["role"] == "user"
    assert data[0]["content"] == "What is PE ratio?"
    assert "timestamp" in data[0]
    assert data[0]["metadata"] == {}


def test_add_message_with_metadata(conversation_history, mock_redis):
    """Test adding message with metadata."""
    mock_redis.get.return_value = None

    metadata = {"source": "yfinance", "tool": "get_price"}
    conversation_history.add_message(
        session_id="session-1",
        role="assistant",
        content="PE ratio is 25.3",
        metadata=metadata
    )

    call_args = mock_redis.setex.call_args
    data = json.loads(call_args[0][2])
    assert data[0]["metadata"] == metadata


def test_add_message_to_existing_history(conversation_history, mock_redis):
    """Test adding message to existing conversation."""
    existing_messages = [
        {
            "role": "user",
            "content": "What is PE?",
            "timestamp": "2026-03-07T10:00:00",
            "metadata": {}
        }
    ]
    mock_redis.get.return_value = json.dumps(existing_messages, ensure_ascii=False)

    conversation_history.add_message(
        session_id="session-1",
        role="assistant",
        content="PE is price-to-earnings ratio"
    )

    call_args = mock_redis.setex.call_args
    data = json.loads(call_args[0][2])
    assert len(data) == 2
    assert data[0]["content"] == "What is PE?"
    assert data[1]["content"] == "PE is price-to-earnings ratio"


def test_get_history_empty(conversation_history, mock_redis):
    """Test getting history when none exists."""
    mock_redis.get.return_value = None

    history = conversation_history.get_history("session-1")
    assert history == []


def test_get_history_with_messages(conversation_history, mock_redis):
    """Test getting conversation history."""
    messages = [
        {"role": "user", "content": "Hello", "timestamp": "2026-03-07T10:00:00", "metadata": {}},
        {"role": "assistant", "content": "Hi", "timestamp": "2026-03-07T10:00:01", "metadata": {}}
    ]
    mock_redis.get.return_value = json.dumps(messages, ensure_ascii=False)

    history = conversation_history.get_history("session-1")
    assert len(history) == 2
    assert history[0]["content"] == "Hello"
    assert history[1]["content"] == "Hi"


def test_get_history_with_limit(conversation_history, mock_redis):
    """Test getting limited history."""
    messages = [
        {"role": "user", "content": "Msg 1", "timestamp": "2026-03-07T10:00:00", "metadata": {}},
        {"role": "assistant", "content": "Msg 2", "timestamp": "2026-03-07T10:00:01", "metadata": {}},
        {"role": "user", "content": "Msg 3", "timestamp": "2026-03-07T10:00:02", "metadata": {}},
        {"role": "assistant", "content": "Msg 4", "timestamp": "2026-03-07T10:00:03", "metadata": {}}
    ]
    mock_redis.get.return_value = json.dumps(messages, ensure_ascii=False)

    history = conversation_history.get_history("session-1", limit=2)
    assert len(history) == 2
    assert history[0]["content"] == "Msg 3"
    assert history[1]["content"] == "Msg 4"


def test_get_history_invalid_json(conversation_history, mock_redis):
    """Test handling invalid JSON in Redis."""
    mock_redis.get.return_value = "invalid json {"

    history = conversation_history.get_history("session-1")
    assert history == []


def test_get_context_empty(conversation_history, mock_redis):
    """Test getting context when no history exists."""
    mock_redis.get.return_value = None

    context = conversation_history.get_context("session-1")
    assert context == ""


def test_get_context_with_messages(conversation_history, mock_redis):
    """Test getting formatted context."""
    messages = [
        {"role": "user", "content": "What is PE?", "timestamp": "2026-03-07T10:00:00", "metadata": {}},
        {"role": "assistant", "content": "PE is price-to-earnings ratio", "timestamp": "2026-03-07T10:00:01", "metadata": {}}
    ]
    mock_redis.get.return_value = json.dumps(messages, ensure_ascii=False)

    context = conversation_history.get_context("session-1")
    assert "Previous conversation:" in context
    assert "User: What is PE?" in context
    assert "Assistant: PE is price-to-earnings ratio" in context


def test_get_context_respects_max_turns(conversation_history, mock_redis):
    """Test context respects max_turns parameter."""
    messages = [
        {"role": "user", "content": "Msg 1", "timestamp": "2026-03-07T10:00:00", "metadata": {}},
        {"role": "assistant", "content": "Msg 2", "timestamp": "2026-03-07T10:00:01", "metadata": {}},
        {"role": "user", "content": "Msg 3", "timestamp": "2026-03-07T10:00:02", "metadata": {}},
        {"role": "assistant", "content": "Msg 4", "timestamp": "2026-03-07T10:00:03", "metadata": {}},
        {"role": "user", "content": "Msg 5", "timestamp": "2026-03-07T10:00:04", "metadata": {}},
        {"role": "assistant", "content": "Msg 6", "timestamp": "2026-03-07T10:00:05", "metadata": {}}
    ]
    mock_redis.get.return_value = json.dumps(messages, ensure_ascii=False)

    context = conversation_history.get_context("session-1", max_turns=2)
    # max_turns=2 means 2 turns = 4 messages (2 user + 2 assistant)
    assert "Msg 1" not in context
    assert "Msg 2" not in context
    assert "Msg 3" in context
    assert "Msg 4" in context
    assert "Msg 5" in context
    assert "Msg 6" in context


def test_clear_history(conversation_history, mock_redis):
    """Test clearing conversation history."""
    conversation_history.clear_history("session-1")

    mock_redis.delete.assert_called_once_with("conversation:session-1")


def test_get_last_user_message(conversation_history, mock_redis):
    """Test getting last user message."""
    messages = [
        {"role": "user", "content": "First question", "timestamp": "2026-03-07T10:00:00", "metadata": {}},
        {"role": "assistant", "content": "First answer", "timestamp": "2026-03-07T10:00:01", "metadata": {}},
        {"role": "user", "content": "Second question", "timestamp": "2026-03-07T10:00:02", "metadata": {}}
    ]
    mock_redis.get.return_value = json.dumps(messages, ensure_ascii=False)

    last_message = conversation_history.get_last_user_message("session-1")
    assert last_message == "Second question"


def test_get_last_user_message_empty(conversation_history, mock_redis):
    """Test getting last user message when none exists."""
    mock_redis.get.return_value = None

    last_message = conversation_history.get_last_user_message("session-1")
    assert last_message is None


def test_get_last_user_message_only_assistant(conversation_history, mock_redis):
    """Test getting last user message when only assistant messages exist."""
    messages = [
        {"role": "assistant", "content": "Hello", "timestamp": "2026-03-07T10:00:00", "metadata": {}}
    ]
    mock_redis.get.return_value = json.dumps(messages, ensure_ascii=False)

    last_message = conversation_history.get_last_user_message("session-1")
    assert last_message is None


def test_is_follow_up_question_no_history(conversation_history, mock_redis):
    """Test follow-up detection with no history."""
    mock_redis.get.return_value = None

    is_follow_up = conversation_history.is_follow_up_question("session-1", "What is PE?")
    assert is_follow_up is False


def test_is_follow_up_question_insufficient_history(conversation_history, mock_redis):
    """Test follow-up detection with insufficient history."""
    messages = [
        {"role": "user", "content": "Hello", "timestamp": "2026-03-07T10:00:00", "metadata": {}}
    ]
    mock_redis.get.return_value = json.dumps(messages, ensure_ascii=False)

    is_follow_up = conversation_history.is_follow_up_question("session-1", "What is PE?")
    assert is_follow_up is False


def test_is_follow_up_question_with_chinese_pronouns(conversation_history, mock_redis):
    """Test follow-up detection with Chinese pronouns."""
    messages = [
        {"role": "user", "content": "特斯拉的股价", "timestamp": "2026-03-07T10:00:00", "metadata": {}},
        {"role": "assistant", "content": "特斯拉股价是250美元", "timestamp": "2026-03-07T10:00:01", "metadata": {}}
    ]
    mock_redis.get.return_value = json.dumps(messages, ensure_ascii=False)

    # Test with Chinese pronouns
    assert conversation_history.is_follow_up_question("session-1", "它的市盈率是多少？") is True
    assert conversation_history.is_follow_up_question("session-1", "这个公司的营收呢？") is True
    assert conversation_history.is_follow_up_question("session-1", "那个股票怎么样？") is True


def test_is_follow_up_question_with_english_pronouns(conversation_history, mock_redis):
    """Test follow-up detection with English pronouns."""
    messages = [
        {"role": "user", "content": "Tesla stock price", "timestamp": "2026-03-07T10:00:00", "metadata": {}},
        {"role": "assistant", "content": "Tesla is at $250", "timestamp": "2026-03-07T10:00:01", "metadata": {}}
    ]
    mock_redis.get.return_value = json.dumps(messages, ensure_ascii=False)

    assert conversation_history.is_follow_up_question("session-1", "What about its PE?") is True
    assert conversation_history.is_follow_up_question("session-1", "How is it performing?") is True
    assert conversation_history.is_follow_up_question("session-1", "Tell me more about this") is True


def test_is_follow_up_question_short_query(conversation_history, mock_redis):
    """Test follow-up detection with short queries."""
    messages = [
        {"role": "user", "content": "Tesla", "timestamp": "2026-03-07T10:00:00", "metadata": {}},
        {"role": "assistant", "content": "Tesla info", "timestamp": "2026-03-07T10:00:01", "metadata": {}}
    ]
    mock_redis.get.return_value = json.dumps(messages, ensure_ascii=False)

    # Short queries are likely follow-ups
    assert conversation_history.is_follow_up_question("session-1", "PE?") is True
    assert conversation_history.is_follow_up_question("session-1", "价格") is True


def test_is_follow_up_question_long_independent_query(conversation_history, mock_redis):
    """Test that long independent queries are not follow-ups."""
    messages = [
        {"role": "user", "content": "Tesla stock", "timestamp": "2026-03-07T10:00:00", "metadata": {}},
        {"role": "assistant", "content": "Tesla info", "timestamp": "2026-03-07T10:00:01", "metadata": {}}
    ]
    mock_redis.get.return_value = json.dumps(messages, ensure_ascii=False)

    # Long query without pronouns should not be follow-up
    is_follow_up = conversation_history.is_follow_up_question(
        "session-1",
        "What is Apple's current stock price and market cap?"
    )
    assert is_follow_up is False


def test_resolve_references_not_follow_up(conversation_history, mock_redis):
    """Test reference resolution when not a follow-up."""
    messages = [
        {"role": "user", "content": "Tesla", "timestamp": "2026-03-07T10:00:00", "metadata": {}},
        {"role": "assistant", "content": "Info", "timestamp": "2026-03-07T10:00:01", "metadata": {}}
    ]
    mock_redis.get.return_value = json.dumps(messages, ensure_ascii=False)

    query = "What is Apple's stock price?"
    resolved = conversation_history.resolve_references("session-1", query)
    assert resolved == query  # Should return unchanged


def test_resolve_references_with_chinese_pronouns(conversation_history, mock_redis):
    """Test reference resolution with Chinese pronouns."""
    messages = [
        {"role": "user", "content": "特斯拉的股价", "timestamp": "2026-03-07T10:00:00", "metadata": {}},
        {"role": "assistant", "content": "250美元", "timestamp": "2026-03-07T10:00:01", "metadata": {}}
    ]
    mock_redis.get.return_value = json.dumps(messages, ensure_ascii=False)

    query = "它的市盈率是多少？"
    resolved = conversation_history.resolve_references("session-1", query)

    # Should prepend context
    assert "特斯拉的股价" in resolved
    assert "它的市盈率是多少？" in resolved


def test_resolve_references_no_last_message(conversation_history, mock_redis):
    """Test reference resolution when no last message exists."""
    mock_redis.get.return_value = None

    query = "它的价格"
    resolved = conversation_history.resolve_references("session-1", query)
    assert resolved == query  # Should return unchanged


def test_get_session_stats_empty(conversation_history, mock_redis):
    """Test session stats for empty session."""
    mock_redis.get.return_value = None

    stats = conversation_history.get_session_stats("session-1")
    assert stats["message_count"] == 0
    assert stats["user_messages"] == 0
    assert stats["assistant_messages"] == 0
    assert stats["duration_seconds"] == 0


def test_get_session_stats_with_messages(conversation_history, mock_redis):
    """Test session stats calculation."""
    messages = [
        {"role": "user", "content": "Q1", "timestamp": "2026-03-07T10:00:00", "metadata": {}},
        {"role": "assistant", "content": "A1", "timestamp": "2026-03-07T10:00:05", "metadata": {}},
        {"role": "user", "content": "Q2", "timestamp": "2026-03-07T10:00:10", "metadata": {}},
        {"role": "assistant", "content": "A2", "timestamp": "2026-03-07T10:00:20", "metadata": {}},
        {"role": "user", "content": "Q3", "timestamp": "2026-03-07T10:00:30", "metadata": {}}
    ]
    mock_redis.get.return_value = json.dumps(messages, ensure_ascii=False)

    stats = conversation_history.get_session_stats("session-1")
    assert stats["message_count"] == 5
    assert stats["user_messages"] == 3
    assert stats["assistant_messages"] == 2
    assert stats["duration_seconds"] == 30  # 10:00:30 - 10:00:00
