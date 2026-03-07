"""Conversation history management with Redis."""
import json
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import redis

from app.config import settings


class ConversationHistory:
    """
    Manages conversation history with Redis storage.

    Features:
    - Store conversation messages by session ID
    - Retrieve recent conversation context
    - Automatic expiration of old conversations
    - Context-aware follow-up question handling
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        Initialize conversation history manager.

        Args:
            redis_client: Redis client instance (creates new if None)
        """
        if redis_client:
            self.redis = redis_client
        else:
            self.redis = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True
            )

        # Default TTL for conversations (24 hours)
        self.ttl = 86400

    def _get_key(self, session_id: str) -> str:
        """Get Redis key for session."""
        return f"conversation:{session_id}"

    def add_message(self, session_id: str, role: str, content: str, metadata: Optional[Dict] = None):
        """
        Add a message to conversation history.

        Args:
            session_id: Unique session identifier
            role: Message role ('user' or 'assistant')
            content: Message content
            metadata: Optional metadata (sources, tools used, etc.)
        """
        key = self._get_key(session_id)

        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }

        # Get existing messages
        messages = self.get_history(session_id)
        messages.append(message)

        # Store updated history
        self.redis.setex(
            key,
            self.ttl,
            json.dumps(messages, ensure_ascii=False)
        )

    def get_history(self, session_id: str, limit: Optional[int] = None) -> List[Dict]:
        """
        Get conversation history for a session.

        Args:
            session_id: Session identifier
            limit: Maximum number of recent messages to return

        Returns:
            List of message dictionaries
        """
        key = self._get_key(session_id)
        data = self.redis.get(key)

        if not data:
            return []

        try:
            messages = json.loads(data)
            if limit:
                return messages[-limit:]
            return messages
        except json.JSONDecodeError:
            return []

    def get_context(self, session_id: str, max_turns: int = 3) -> str:
        """
        Get formatted conversation context for LLM.

        Args:
            session_id: Session identifier
            max_turns: Maximum number of conversation turns to include

        Returns:
            Formatted context string
        """
        messages = self.get_history(session_id, limit=max_turns * 2)

        if not messages:
            return ""

        context_parts = ["Previous conversation:"]
        for msg in messages:
            role = "User" if msg["role"] == "user" else "Assistant"
            context_parts.append(f"{role}: {msg['content']}")

        return "\n".join(context_parts)

    def clear_history(self, session_id: str):
        """
        Clear conversation history for a session.

        Args:
            session_id: Session identifier
        """
        key = self._get_key(session_id)
        self.redis.delete(key)

    def get_last_user_message(self, session_id: str) -> Optional[str]:
        """
        Get the last user message from history.

        Args:
            session_id: Session identifier

        Returns:
            Last user message content or None
        """
        messages = self.get_history(session_id)

        for msg in reversed(messages):
            if msg["role"] == "user":
                return msg["content"]

        return None

    def is_follow_up_question(self, session_id: str, current_query: str) -> bool:
        """
        Determine if current query is a follow-up question.

        Args:
            session_id: Session identifier
            current_query: Current user query

        Returns:
            True if query appears to be a follow-up
        """
        # Check if there's conversation history
        messages = self.get_history(session_id)
        if len(messages) < 2:
            return False

        # Follow-up indicators
        follow_up_markers = {
            "它", "他", "她", "这个", "那个", "这", "那",
            "it", "this", "that", "its", "the same"
        }

        query_lower = current_query.lower()

        # Check for pronouns or references
        if any(marker in query_lower for marker in follow_up_markers):
            return True

        # Check if query is very short (likely a follow-up)
        if len(current_query) < 10:
            return True

        return False

    def resolve_references(self, session_id: str, current_query: str) -> str:
        """
        Resolve references in follow-up questions.

        Args:
            session_id: Session identifier
            current_query: Current query with potential references

        Returns:
            Query with resolved references
        """
        if not self.is_follow_up_question(session_id, current_query):
            return current_query

        # Get last user message for context
        last_message = self.get_last_user_message(session_id)
        if not last_message:
            return current_query

        # Simple reference resolution
        # Replace pronouns with context from last message
        resolved = current_query

        # Extract potential entities from last message (simple approach)
        # In production, use NER or more sophisticated methods
        if "它" in resolved or "这个" in resolved or "那个" in resolved:
            # Add context from previous question
            resolved = f"{last_message}，{resolved}"

        return resolved

    def get_session_stats(self, session_id: str) -> Dict:
        """
        Get statistics for a conversation session.

        Args:
            session_id: Session identifier

        Returns:
            Dictionary with session statistics
        """
        messages = self.get_history(session_id)

        if not messages:
            return {
                "message_count": 0,
                "user_messages": 0,
                "assistant_messages": 0,
                "duration_seconds": 0
            }

        user_count = sum(1 for m in messages if m["role"] == "user")
        assistant_count = sum(1 for m in messages if m["role"] == "assistant")

        # Calculate duration
        first_time = datetime.fromisoformat(messages[0]["timestamp"])
        last_time = datetime.fromisoformat(messages[-1]["timestamp"])
        duration = (last_time - first_time).total_seconds()

        return {
            "message_count": len(messages),
            "user_messages": user_count,
            "assistant_messages": assistant_count,
            "duration_seconds": duration
        }
