"""Session memory for multi-turn conversations."""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class ConversationTurn:
    """Single conversation turn."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: str
    tools_used: List[str] = None
    symbols_mentioned: List[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationTurn":
        """Create from dictionary."""
        return cls(**data)


class SessionMemory:
    """Two-layer session memory for multi-turn conversations.

    Layer 1: Redis (short-term, TTL 30 minutes)
    - Fast access for active sessions
    - Automatic expiration

    Layer 2: PostgreSQL (long-term, persistent)
    - User profile and preferences
    - Historical conversation data
    - Analytics and learning

    For MVP, we implement Layer 1 only using in-memory storage
    with Redis as optional backend.
    """

    def __init__(self):
        self.sessions: Dict[str, List[ConversationTurn]] = {}
        self.session_ttl = timedelta(minutes=30)
        self.session_timestamps: Dict[str, datetime] = {}

        # Try to connect to Redis if available
        self.redis_client = None
        try:
            import redis
            from app.config import settings
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True
            )
            self.redis_client.ping()
            logger.info("[SessionMemory] Connected to Redis for session storage")
        except Exception as e:
            logger.warning(
                f"[SessionMemory] Redis not available, using in-memory storage: {e}"
            )

    async def save_turn(
        self,
        session_id: str,
        user_id: Optional[str],
        turn: ConversationTurn
    ):
        """Save a conversation turn.

        Args:
            session_id: Session identifier
            user_id: User identifier (optional)
            turn: ConversationTurn to save
        """
        # Update timestamp
        self.session_timestamps[session_id] = datetime.now()

        # Save to memory
        if session_id not in self.sessions:
            self.sessions[session_id] = []

        self.sessions[session_id].append(turn)

        # Save to Redis if available
        if self.redis_client:
            try:
                key = f"session:{session_id}"
                value = json.dumps(turn.to_dict())

                # Use LPUSH to prepend (newest first)
                self.redis_client.lpush(key, value)

                # Set expiration
                self.redis_client.expire(key, int(self.session_ttl.total_seconds()))

            except Exception as e:
                logger.warning(f"[SessionMemory] Failed to save to Redis: {e}")

    async def get_context(
        self,
        session_id: str,
        max_turns: int = 5
    ) -> List[ConversationTurn]:
        """Get recent conversation context.

        Args:
            session_id: Session identifier
            max_turns: Maximum number of turns to retrieve

        Returns:
            List of recent ConversationTurns (newest first)
        """
        # Try Redis first
        if self.redis_client:
            try:
                key = f"session:{session_id}"
                values = self.redis_client.lrange(key, 0, max_turns - 1)

                if values:
                    turns = [
                        ConversationTurn.from_dict(json.loads(v))
                        for v in values
                    ]
                    return turns

            except Exception as e:
                logger.warning(f"[SessionMemory] Failed to read from Redis: {e}")

        # Fallback to memory
        if session_id in self.sessions:
            turns = self.sessions[session_id]
            return turns[-max_turns:][::-1]  # Last N turns, reversed

        return []

    async def clear_session(self, session_id: str):
        """Clear a session.

        Args:
            session_id: Session identifier
        """
        # Clear from memory
        if session_id in self.sessions:
            del self.sessions[session_id]

        if session_id in self.session_timestamps:
            del self.session_timestamps[session_id]

        # Clear from Redis
        if self.redis_client:
            try:
                key = f"session:{session_id}"
                self.redis_client.delete(key)
            except Exception as e:
                logger.warning(f"[SessionMemory] Failed to clear Redis: {e}")

    async def cleanup_expired_sessions(self):
        """Remove expired sessions from memory."""
        now = datetime.now()
        expired = []

        for session_id, timestamp in self.session_timestamps.items():
            if now - timestamp > self.session_ttl:
                expired.append(session_id)

        for session_id in expired:
            await self.clear_session(session_id)
            logger.info(f"[SessionMemory] Cleaned up expired session: {session_id}")

    def resolve_references(
        self,
        query: str,
        context: List[ConversationTurn]
    ) -> str:
        """Resolve pronoun references using conversation context.

        Examples:
            "那它的估值呢？" + context[AAPL] -> "AAPL的估值呢？"
            "它最近表现如何？" + context[TSLA] -> "TSLA最近表现如何？"

        Args:
            query: Current user query
            context: Recent conversation turns

        Returns:
            Query with resolved references
        """
        # Simple reference resolution
        pronouns = ["它", "他", "她", "这个", "那个", "这只", "那只"]

        # Check if query contains pronouns
        has_pronoun = any(p in query for p in pronouns)

        if not has_pronoun:
            return query

        # Extract symbols from recent context
        recent_symbols = []
        for turn in context:
            if turn.symbols_mentioned:
                recent_symbols.extend(turn.symbols_mentioned)

        # Use most recent symbol
        if recent_symbols:
            most_recent = recent_symbols[-1]

            # Replace pronouns
            resolved = query
            for pronoun in pronouns:
                if pronoun in resolved:
                    resolved = resolved.replace(pronoun, most_recent)
                    logger.info(
                        f"[SessionMemory] Resolved reference: "
                        f"'{query}' -> '{resolved}'"
                    )
                    return resolved

        return query

    def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """Get session information.

        Args:
            session_id: Session identifier

        Returns:
            Session info dictionary
        """
        turn_count = len(self.sessions.get(session_id, []))
        timestamp = self.session_timestamps.get(session_id)

        return {
            "session_id": session_id,
            "turn_count": turn_count,
            "last_active": timestamp.isoformat() if timestamp else None,
            "storage": "redis" if self.redis_client else "memory"
        }


# Global instance
session_memory = SessionMemory()


# Background cleanup task
async def start_cleanup_task():
    """Start background task to cleanup expired sessions."""
    while True:
        try:
            await session_memory.cleanup_expired_sessions()
        except Exception as e:
            logger.error(f"[SessionMemory] Cleanup task error: {e}")

        # Run every 5 minutes
        await asyncio.sleep(300)
