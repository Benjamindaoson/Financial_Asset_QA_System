"""
Feedback Collector for GraphRAG.

This module provides comprehensive feedback collection mechanisms
for gathering user interactions, satisfaction ratings, and improvement suggestions.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime
import json
import uuid
from enum import Enum

logger = logging.getLogger(__name__)


class FeedbackType(Enum):
    """Types of user feedback."""
    RATING = "rating"           # Numerical rating (1-5)
    THUMBS_UP_DOWN = "thumbs"   # Binary feedback
    TEXT_COMMENT = "comment"    # Free-text feedback
    CORRECTION = "correction"   # User correction to answer
    FEATURE_REQUEST = "feature" # Feature suggestions
    BUG_REPORT = "bug"         # Bug reports


class FeedbackChannel(Enum):
    """Channels for collecting feedback."""
    API = "api"                 # Direct API calls
    UI_WIDGET = "ui_widget"     # UI feedback widgets
    EMAIL = "email"            # Email feedback
    SURVEY = "survey"          # Structured surveys
    LOG_ANALYSIS = "logs"      # Implicit feedback from logs


class FeedbackItem:
    """
    Individual feedback item with metadata.
    """

    def __init__(
        self,
        feedback_type: FeedbackType,
        content: Any,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        query_id: Optional[str] = None,
        channel: FeedbackChannel = FeedbackChannel.API,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize feedback item.

        Args:
            feedback_type: Type of feedback
            content: Feedback content
            user_id: User identifier
            session_id: Session identifier
            query_id: Associated query ID
            channel: Feedback collection channel
            metadata: Additional metadata
        """
        self.id = str(uuid.uuid4())
        self.feedback_type = feedback_type
        self.content = content
        self.user_id = user_id or "anonymous"
        self.session_id = session_id or str(uuid.uuid4())
        self.query_id = query_id
        self.channel = channel
        self.timestamp = datetime.utcnow()
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'id': self.id,
            'feedback_type': self.feedback_type.value,
            'content': self.content,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'query_id': self.query_id,
            'channel': self.channel.value,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FeedbackItem':
        """Create from dictionary."""
        return cls(
            feedback_type=FeedbackType(data['feedback_type']),
            content=data['content'],
            user_id=data.get('user_id'),
            session_id=data.get('session_id'),
            query_id=data.get('query_id'),
            channel=FeedbackChannel(data.get('channel', 'api')),
            metadata=data.get('metadata', {})
        )


class FeedbackCollector:
    """
    Collects and manages user feedback from multiple channels.
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize feedback collector.

        Args:
            storage_path: Path to store feedback data
        """
        self.storage_path = storage_path or "artifacts/feedback"
        self.feedback_buffer = []
        self.buffer_size = 100  # Batch size for storage

        # Create storage directory if it doesn't exist
        import os
        os.makedirs(self.storage_path, exist_ok=True)

        logger.info(f"Feedback collector initialized with storage: {self.storage_path}")

    def collect_rating_feedback(
        self,
        rating: int,
        query_id: str,
        user_id: Optional[str] = None,
        comments: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Collect numerical rating feedback.

        Args:
            rating: Rating value (1-5)
            query_id: Associated query ID
            user_id: User identifier
            comments: Optional comments
            metadata: Additional metadata

        Returns:
            Feedback item ID
        """
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5")

        content = {'rating': rating}
        if comments:
            content['comments'] = comments

        feedback = FeedbackItem(
            feedback_type=FeedbackType.RATING,
            content=content,
            user_id=user_id,
            query_id=query_id,
            metadata=metadata
        )

        return self._store_feedback(feedback)

    def collect_thumbs_feedback(
        self,
        is_positive: bool,
        query_id: str,
        user_id: Optional[str] = None,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Collect thumbs up/down feedback.

        Args:
            is_positive: True for thumbs up, False for thumbs down
            query_id: Associated query ID
            user_id: User identifier
            reason: Optional reason for feedback
            metadata: Additional metadata

        Returns:
            Feedback item ID
        """
        content = {'thumbs_up': is_positive}
        if reason:
            content['reason'] = reason

        feedback = FeedbackItem(
            feedback_type=FeedbackType.THUMBS_UP_DOWN,
            content=content,
            user_id=user_id,
            query_id=query_id,
            metadata=metadata
        )

        return self._store_feedback(feedback)

    def collect_text_feedback(
        self,
        comment: str,
        feedback_type: FeedbackType = FeedbackType.TEXT_COMMENT,
        query_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Collect text-based feedback.

        Args:
            comment: Text feedback
            feedback_type: Type of text feedback
            query_id: Associated query ID
            user_id: User identifier
            metadata: Additional metadata

        Returns:
            Feedback item ID
        """
        feedback = FeedbackItem(
            feedback_type=feedback_type,
            content={'text': comment},
            user_id=user_id,
            query_id=query_id,
            metadata=metadata
        )

        return self._store_feedback(feedback)

    def collect_correction_feedback(
        self,
        original_answer: str,
        corrected_answer: str,
        query_id: str,
        user_id: Optional[str] = None,
        explanation: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Collect answer correction feedback.

        Args:
            original_answer: System's original answer
            corrected_answer: User's corrected answer
            query_id: Associated query ID
            user_id: User identifier
            explanation: Explanation for correction
            metadata: Additional metadata

        Returns:
            Feedback item ID
        """
        content = {
            'original_answer': original_answer,
            'corrected_answer': corrected_answer,
            'similarity': self._calculate_text_similarity(original_answer, corrected_answer)
        }
        if explanation:
            content['explanation'] = explanation

        feedback = FeedbackItem(
            feedback_type=FeedbackType.CORRECTION,
            content=content,
            user_id=user_id,
            query_id=query_id,
            metadata=metadata
        )

        return self._store_feedback(feedback)

    def collect_implicit_feedback(
        self,
        action: str,
        query_id: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Collect implicit feedback from user behavior.

        Args:
            action: User action (e.g., 'answer_viewed', 'answer_copied', 'follow_up_query')
            query_id: Associated query ID
            user_id: User identifier
            metadata: Additional metadata

        Returns:
            Feedback item ID
        """
        feedback = FeedbackItem(
            feedback_type=FeedbackType.TEXT_COMMENT,  # Using comment type for implicit
            content={'action': action, 'implicit': True},
            user_id=user_id,
            query_id=query_id,
            channel=FeedbackChannel.LOG_ANALYSIS,
            metadata=metadata
        )

        return self._store_feedback(feedback)

    def _store_feedback(self, feedback: FeedbackItem) -> str:
        """
        Store feedback item.

        Args:
            feedback: Feedback item to store

        Returns:
            Feedback item ID
        """
        # Add to buffer
        self.feedback_buffer.append(feedback)

        # Flush buffer if full
        if len(self.feedback_buffer) >= self.buffer_size:
            self._flush_buffer()

        logger.debug(f"Collected feedback: {feedback.feedback_type.value} from {feedback.user_id}")
        return feedback.id

    def _flush_buffer(self):
        """Flush feedback buffer to storage."""
        if not self.feedback_buffer:
            return

        try:
            # Create filename with timestamp
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"feedback_{timestamp}.jsonl"
            filepath = f"{self.storage_path}/{filename}"

            # Write to file
            with open(filepath, 'w', encoding='utf-8') as f:
                for feedback in self.feedback_buffer:
                    f.write(json.dumps(feedback.to_dict(), ensure_ascii=False) + '\n')

            logger.info(f"Flushed {len(self.feedback_buffer)} feedback items to {filepath}")

        except Exception as e:
            logger.error(f"Failed to flush feedback buffer: {e}")

        finally:
            self.feedback_buffer.clear()

    def get_recent_feedback(
        self,
        hours: int = 24,
        feedback_type: Optional[FeedbackType] = None,
        limit: int = 100
    ) -> List[FeedbackItem]:
        """
        Get recent feedback items.

        Args:
            hours: Number of hours to look back
            feedback_type: Filter by feedback type
            limit: Maximum number of items to return

        Returns:
            List of recent feedback items
        """
        import glob
        import os
        from datetime import timedelta

        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_feedback = []

        try:
            # Find recent feedback files
            feedback_files = glob.glob(f"{self.storage_path}/feedback_*.jsonl")
            feedback_files.sort(reverse=True)  # Most recent first

            for filepath in feedback_files[:5]:  # Check last 5 files
                if os.path.exists(filepath):
                    with open(filepath, 'r', encoding='utf-8') as f:
                        for line in f:
                            try:
                                data = json.loads(line.strip())
                                item = FeedbackItem.from_dict(data)

                                # Check time filter
                                if item.timestamp >= cutoff_time:
                                    # Check type filter
                                    if feedback_type is None or item.feedback_type == feedback_type:
                                        recent_feedback.append(item)

                                        if len(recent_feedback) >= limit:
                                            break

                            except json.JSONDecodeError:
                                continue

                if len(recent_feedback) >= limit:
                    break

        except Exception as e:
            logger.error(f"Failed to get recent feedback: {e}")

        return recent_feedback

    def get_feedback_stats(
        self,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get feedback statistics.

        Args:
            hours: Number of hours to analyze

        Returns:
            Feedback statistics
        """
        feedback_items = self.get_recent_feedback(hours=hours, limit=10000)

        stats = {
            'total_feedback': len(feedback_items),
            'time_period_hours': hours,
            'feedback_types': {},
            'channels': {},
            'avg_rating': None,
            'thumbs_up_ratio': None
        }

        ratings = []
        thumbs_feedback = []

        for item in feedback_items:
            # Count types
            fb_type = item.feedback_type.value
            stats['feedback_types'][fb_type] = stats['feedback_types'].get(fb_type, 0) + 1

            # Count channels
            channel = item.channel.value
            stats['channels'][channel] = stats['channels'].get(channel, 0) + 1

            # Collect ratings
            if item.feedback_type == FeedbackType.RATING:
                rating = item.content.get('rating')
                if rating:
                    ratings.append(rating)

            # Collect thumbs feedback
            elif item.feedback_type == FeedbackType.THUMBS_UP_DOWN:
                thumbs_up = item.content.get('thumbs_up')
                if thumbs_up is not None:
                    thumbs_feedback.append(thumbs_up)

        # Calculate averages
        if ratings:
            stats['avg_rating'] = sum(ratings) / len(ratings)

        if thumbs_feedback:
            stats['thumbs_up_ratio'] = sum(thumbs_feedback) / len(thumbs_feedback)

        return stats

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity."""
        # Jaccard similarity on words
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 and not words2:
            return 1.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def shutdown(self):
        """Shutdown feedback collector and flush remaining buffer."""
        self._flush_buffer()
        logger.info("Feedback collector shutdown")







