"""Test session memory functionality."""

import pytest
from app.session.memory import SessionMemory, ConversationTurn


class TestSessionMemory:
    """Test suite for SessionMemory."""

    @pytest.fixture
    def memory(self):
        """Create SessionMemory instance."""
        return SessionMemory()

    @pytest.fixture
    def sample_turn(self):
        """Create sample conversation turn."""
        return ConversationTurn(
            role="user",
            content="AAPL最新价格是多少？",
            timestamp="2024-01-01T10:00:00Z",
            tools_used=["get_price"],
            symbols_mentioned=["AAPL"]
        )

    @pytest.mark.asyncio
    async def test_save_and_retrieve_turn(self, memory, sample_turn):
        """Test saving and retrieving conversation turns."""
        session_id = "test-session-001"

        # Save turn
        await memory.save_turn(session_id, "user-123", sample_turn)

        # Retrieve context
        context = await memory.get_context(session_id, max_turns=5)

        assert len(context) == 1
        assert context[0].content == sample_turn.content
        assert context[0].role == sample_turn.role

    @pytest.mark.asyncio
    async def test_multiple_turns(self, memory):
        """Test multiple conversation turns."""
        session_id = "test-session-002"

        # Add multiple turns
        turns = [
            ConversationTurn(
                role="user",
                content="AAPL价格",
                timestamp="2024-01-01T10:00:00Z",
                symbols_mentioned=["AAPL"]
            ),
            ConversationTurn(
                role="assistant",
                content="AAPL当前价格是$150",
                timestamp="2024-01-01T10:00:01Z",
                tools_used=["get_price"]
            ),
            ConversationTurn(
                role="user",
                content="它的市盈率呢？",
                timestamp="2024-01-01T10:00:05Z"
            )
        ]

        for turn in turns:
            await memory.save_turn(session_id, "user-123", turn)

        # Retrieve context
        context = await memory.get_context(session_id, max_turns=5)

        assert len(context) == 3

    @pytest.mark.asyncio
    async def test_max_turns_limit(self, memory):
        """Test max_turns parameter."""
        session_id = "test-session-003"

        # Add 10 turns
        for i in range(10):
            turn = ConversationTurn(
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
                timestamp=f"2024-01-01T10:00:{i:02d}Z"
            )
            await memory.save_turn(session_id, "user-123", turn)

        # Retrieve only last 3 turns
        context = await memory.get_context(session_id, max_turns=3)

        assert len(context) == 3

    @pytest.mark.asyncio
    async def test_clear_session(self, memory, sample_turn):
        """Test clearing a session."""
        session_id = "test-session-004"

        # Add turn
        await memory.save_turn(session_id, "user-123", sample_turn)

        # Verify it exists
        context = await memory.get_context(session_id)
        assert len(context) == 1

        # Clear session
        await memory.clear_session(session_id)

        # Verify it's cleared
        context = await memory.get_context(session_id)
        assert len(context) == 0

    def test_resolve_references_simple(self, memory):
        """Test simple pronoun reference resolution."""
        context = [
            ConversationTurn(
                role="user",
                content="AAPL价格",
                timestamp="2024-01-01T10:00:00Z",
                symbols_mentioned=["AAPL"]
            )
        ]

        # Test pronoun resolution
        query = "它的市盈率呢？"
        resolved = memory.resolve_references(query, context)

        assert "AAPL" in resolved
        assert "它" not in resolved

    def test_resolve_references_no_context(self, memory):
        """Test reference resolution with no context."""
        query = "它的市盈率呢？"
        resolved = memory.resolve_references(query, [])

        # Should return original query if no context
        assert resolved == query

    def test_resolve_references_no_pronouns(self, memory):
        """Test query without pronouns."""
        context = [
            ConversationTurn(
                role="user",
                content="AAPL价格",
                timestamp="2024-01-01T10:00:00Z",
                symbols_mentioned=["AAPL"]
            )
        ]

        query = "MSFT的价格是多少？"
        resolved = memory.resolve_references(query, context)

        # Should return original query
        assert resolved == query

    def test_get_session_info(self, memory, sample_turn):
        """Test getting session information."""
        session_id = "test-session-005"

        # Initially empty
        info = memory.get_session_info(session_id)
        assert info["turn_count"] == 0
        assert info["last_active"] is None

        # After adding turn
        import asyncio
        asyncio.run(memory.save_turn(session_id, "user-123", sample_turn))

        info = memory.get_session_info(session_id)
        assert info["turn_count"] == 1
        assert info["last_active"] is not None
        assert info["storage"] in ["redis", "memory"]

    def test_conversation_turn_serialization(self):
        """Test ConversationTurn serialization."""
        turn = ConversationTurn(
            role="user",
            content="Test message",
            timestamp="2024-01-01T10:00:00Z",
            tools_used=["tool1", "tool2"],
            symbols_mentioned=["AAPL"]
        )

        # To dict
        data = turn.to_dict()
        assert data["role"] == "user"
        assert data["content"] == "Test message"
        assert data["tools_used"] == ["tool1", "tool2"]

        # From dict
        restored = ConversationTurn.from_dict(data)
        assert restored.role == turn.role
        assert restored.content == turn.content
        assert restored.tools_used == turn.tools_used
