"""
Feedback Analyzer for GraphRAG.

This module analyzes user feedback to identify patterns, trends, and insights
for improving the GraphRAG system.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
from collections import defaultdict, Counter
import re
from datetime import datetime, timedelta
import numpy as np

from .feedback_collector import FeedbackItem, FeedbackType

logger = logging.getLogger(__name__)


class FeedbackAnalyzer:
    """
    Analyzes user feedback to extract insights and improvement recommendations.
    """

    def __init__(self):
        """Initialize feedback analyzer."""
        self.sentiment_keywords = {
            'positive': ['good', 'great', 'excellent', 'helpful', 'accurate', 'useful', 'perfect', 'amazing'],
            'negative': ['bad', 'wrong', 'incorrect', 'useless', 'confusing', 'poor', 'terrible', 'awful'],
            'neutral': ['okay', 'fine', 'average', 'normal', 'standard']
        }

        self.error_patterns = [
            re.compile(r'(?:wrong|incorrect|error).*?(?:answer|information)', re.IGNORECASE),
            re.compile(r'(?:doesn\'?t|didn\'?t).*?(?:understand|work)', re.IGNORECASE),
            re.compile(r'(?:missing|lack).*?(?:information|data)', re.IGNORECASE),
            re.compile(r'(?:too|very).*?(?:slow|long)', re.IGNORECASE)
        ]

        logger.info("Feedback analyzer initialized")

    def analyze_feedback_batch(
        self,
        feedback_items: List[FeedbackItem],
        analysis_period_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Analyze a batch of feedback items.

        Args:
            feedback_items: List of feedback items to analyze
            analysis_period_hours: Analysis period in hours

        Returns:
            Comprehensive feedback analysis
        """
        analysis = {
            'summary': self._generate_summary_stats(feedback_items),
            'sentiment_analysis': self._analyze_sentiment(feedback_items),
            'error_analysis': self._analyze_errors(feedback_items),
            'trend_analysis': self._analyze_trends(feedback_items, analysis_period_hours),
            'user_segments': self._analyze_user_segments(feedback_items),
            'recommendations': self._generate_recommendations(feedback_items),
            'quality_metrics': self._calculate_quality_metrics(feedback_items)
        }

        return analysis

    def _generate_summary_stats(self, feedback_items: List[FeedbackItem]) -> Dict[str, Any]:
        """Generate summary statistics."""
        if not feedback_items:
            return {'total_feedback': 0, 'avg_rating': None, 'thumbs_up_ratio': None}

        stats = {
            'total_feedback': len(feedback_items),
            'feedback_types': defaultdict(int),
            'channels': defaultdict(int),
            'time_range': {
                'start': min(item.timestamp for item in feedback_items),
                'end': max(item.timestamp for item in feedback_items)
            }
        }

        ratings = []
        thumbs_feedback = []

        for item in feedback_items:
            # Count types and channels
            stats['feedback_types'][item.feedback_type.value] += 1
            stats['channels'][item.channel.value] += 1

            # Collect ratings
            if item.feedback_type == FeedbackType.RATING:
                rating = item.content.get('rating')
                if rating:
                    ratings.append(rating)
            elif item.feedback_type == FeedbackType.THUMBS_UP_DOWN:
                thumbs_up = item.content.get('thumbs_up')
                if thumbs_up is not None:
                    thumbs_feedback.append(thumbs_up)

        # Calculate averages
        stats['avg_rating'] = np.mean(ratings) if ratings else None
        stats['thumbs_up_ratio'] = np.mean(thumbs_feedback) if thumbs_feedback else None
        stats['rating_distribution'] = dict(Counter(ratings)) if ratings else {}

        return dict(stats)  # Convert defaultdict to dict

    def _analyze_sentiment(self, feedback_items: List[FeedbackItem]) -> Dict[str, Any]:
        """Analyze sentiment in feedback."""
        sentiment_scores = {'positive': 0, 'negative': 0, 'neutral': 0}
        sentiment_examples = {'positive': [], 'negative': [], 'neutral': []}

        for item in feedback_items:
            if item.feedback_type in [FeedbackType.TEXT_COMMENT, FeedbackType.CORRECTION]:
                text_content = self._extract_text_content(item)
                if text_content:
                    sentiment = self._classify_sentiment(text_content)
                    sentiment_scores[sentiment] += 1

                    # Store examples (up to 3 per category)
                    if len(sentiment_examples[sentiment]) < 3:
                        sentiment_examples[sentiment].append(text_content[:100])

        total_sentiment_feedback = sum(sentiment_scores.values())

        analysis = {
            'sentiment_distribution': sentiment_scores,
            'sentiment_ratios': {
                k: v / total_sentiment_feedback if total_sentiment_feedback > 0 else 0
                for k, v in sentiment_scores.items()
            },
            'examples': sentiment_examples,
            'overall_sentiment': self._calculate_overall_sentiment(sentiment_scores)
        }

        return analysis

    def _analyze_errors(self, feedback_items: List[FeedbackItem]) -> Dict[str, Any]:
        """Analyze errors and issues mentioned in feedback."""
        error_categories = defaultdict(int)
        error_examples = defaultdict(list)

        for item in feedback_items:
            text_content = self._extract_text_content(item)
            if text_content:
                errors = self._detect_errors(text_content)

                for error_type in errors:
                    error_categories[error_type] += 1

                    # Store examples
                    if len(error_examples[error_type]) < 2:
                        error_examples[error_type].append(text_content[:100])

        # Sort by frequency
        sorted_errors = sorted(error_categories.items(), key=lambda x: x[1], reverse=True)

        analysis = {
            'error_categories': dict(error_categories),
            'most_common_errors': sorted_errors[:5],
            'error_examples': dict(error_examples),
            'error_rate': len([item for item in feedback_items if self._has_errors(item)]) / len(feedback_items)
        }

        return analysis

    def _analyze_trends(self, feedback_items: List[FeedbackItem], hours: int) -> Dict[str, Any]:
        """Analyze feedback trends over time."""
        if not feedback_items:
            return {'trends': [], 'volatility': 0.0}

        # Group by time buckets
        bucket_size = max(1, hours // 24)  # Hourly buckets
        time_buckets = defaultdict(list)

        start_time = min(item.timestamp for item in feedback_items)

        for item in feedback_items:
            hours_diff = (item.timestamp - start_time).total_seconds() / 3600
            bucket = int(hours_diff // bucket_size)
            time_buckets[bucket].append(item)

        # Calculate metrics per bucket
        trends = []
        ratings_over_time = []

        for bucket, items in sorted(time_buckets.items()):
            bucket_ratings = []
            bucket_sentiment = {'positive': 0, 'negative': 0, 'neutral': 0}

            for item in items:
                if item.feedback_type == FeedbackType.RATING:
                    rating = item.content.get('rating')
                    if rating:
                        bucket_ratings.append(rating)
                        ratings_over_time.append(rating)

                # Sentiment analysis
                if item.feedback_type in [FeedbackType.TEXT_COMMENT, FeedbackType.THUMBS_UP_DOWN]:
                    text_content = self._extract_text_content(item)
                    if text_content:
                        sentiment = self._classify_sentiment(text_content)
                        bucket_sentiment[sentiment] += 1

            bucket_stats = {
                'bucket': bucket,
                'start_hour': bucket * bucket_size,
                'feedback_count': len(items),
                'avg_rating': np.mean(bucket_ratings) if bucket_ratings else None,
                'sentiment_distribution': bucket_sentiment
            }
            trends.append(bucket_stats)

        # Calculate trend metrics
        volatility = np.std(ratings_over_time) if len(ratings_over_time) > 1 else 0.0

        # Detect rating trend
        if len(trends) > 1:
            recent_trend = np.polyfit(
                [t['bucket'] for t in trends],
                [t['avg_rating'] or 3.0 for t in trends],  # Default to neutral rating
                1
            )[0]
        else:
            recent_trend = 0.0

        analysis = {
            'trends': trends,
            'volatility': float(volatility),
            'rating_trend': float(recent_trend),
            'trend_direction': 'improving' if recent_trend > 0.01 else 'declining' if recent_trend < -0.01 else 'stable'
        }

        return analysis

    def _analyze_user_segments(self, feedback_items: List[FeedbackItem]) -> Dict[str, Any]:
        """Analyze feedback by user segments."""
        user_feedback = defaultdict(list)

        for item in feedback_items:
            user_feedback[item.user_id].append(item)

        # Analyze user behavior patterns
        user_segments = {
            'power_users': [],      # High frequency users
            'casual_users': [],     # Low frequency users
            'critical_users': [],   # Mostly negative feedback
            'satisfied_users': []   # Mostly positive feedback
        }

        for user_id, items in user_feedback.items():
            feedback_count = len(items)
            avg_rating = self._calculate_user_avg_rating(items)

            if feedback_count >= 10:  # Power users
                user_segments['power_users'].append({
                    'user_id': user_id,
                    'feedback_count': feedback_count,
                    'avg_rating': avg_rating
                })
            elif feedback_count <= 2:  # Casual users
                user_segments['casual_users'].append({
                    'user_id': user_id,
                    'feedback_count': feedback_count,
                    'avg_rating': avg_rating
                })

            # Sentiment-based segmentation
            positive_ratio = self._calculate_user_positive_ratio(items)
            if positive_ratio >= 0.8:
                user_segments['satisfied_users'].append({
                    'user_id': user_id,
                    'positive_ratio': positive_ratio
                })
            elif positive_ratio <= 0.3:
                user_segments['critical_users'].append({
                    'user_id': user_id,
                    'positive_ratio': positive_ratio
                })

        return user_segments

    def _generate_recommendations(self, feedback_items: List[FeedbackItem]) -> List[Dict[str, Any]]:
        """Generate improvement recommendations based on feedback."""
        recommendations = []

        # Analyze common issues
        error_analysis = self._analyze_errors(feedback_items)
        sentiment_analysis = self._analyze_sentiment(feedback_items)

        # Error-based recommendations
        if error_analysis['error_categories'].get('accuracy_error', 0) > 0:
            recommendations.append({
                'type': 'accuracy_improvement',
                'priority': 'high',
                'description': 'Improve answer accuracy based on correction feedback',
                'evidence': error_analysis['error_categories']['accuracy_error'],
                'suggested_action': 'Review and update knowledge base with user corrections'
            })

        # Performance-based recommendations
        if error_analysis['error_categories'].get('speed_issue', 0) > 0:
            recommendations.append({
                'type': 'performance_optimization',
                'priority': 'medium',
                'description': 'Optimize response speed based on user feedback',
                'evidence': error_analysis['error_categories']['speed_issue'],
                'suggested_action': 'Implement response caching and model optimization'
            })

        # Sentiment-based recommendations
        if sentiment_analysis['overall_sentiment'] == 'negative':
            recommendations.append({
                'type': 'user_experience',
                'priority': 'high',
                'description': 'Address user dissatisfaction with system responses',
                'evidence': sentiment_analysis['sentiment_distribution']['negative'],
                'suggested_action': 'Conduct user interviews and improve response quality'
            })

        # Feature requests
        feature_requests = [item for item in feedback_items
                          if item.feedback_type == FeedbackType.FEATURE_REQUEST]
        if feature_requests:
            recommendations.append({
                'type': 'feature_development',
                'priority': 'medium',
                'description': 'Consider implementing requested features',
                'evidence': len(feature_requests),
                'suggested_action': 'Analyze feature requests and prioritize development'
            })

        return recommendations

    def _calculate_quality_metrics(self, feedback_items: List[FeedbackItem]) -> Dict[str, float]:
        """Calculate quality metrics from feedback."""
        if not feedback_items:
            return {'overall_quality': 0.0, 'user_satisfaction': 0.0}

        # Calculate user satisfaction score
        ratings = []
        thumbs_scores = []

        for item in feedback_items:
            if item.feedback_type == FeedbackType.RATING:
                rating = item.content.get('rating')
                if rating:
                    # Normalize to 0-1 scale
                    ratings.append((rating - 1) / 4)  # 1-5 scale to 0-1
            elif item.feedback_type == FeedbackType.THUMBS_UP_DOWN:
                thumbs_up = item.content.get('thumbs_up')
                if thumbs_up is not None:
                    thumbs_scores.append(1.0 if thumbs_up else 0.0)

        # Combine different feedback types
        all_scores = ratings + thumbs_scores
        user_satisfaction = np.mean(all_scores) if all_scores else 0.5

        # Calculate overall quality score
        # Factor in error rate and sentiment
        sentiment_score = self._analyze_sentiment(feedback_items)
        error_penalty = self._analyze_errors(feedback_items)['error_rate']

        overall_quality = user_satisfaction * (1 - error_penalty * 0.3)

        metrics = {
            'overall_quality': float(overall_quality),
            'user_satisfaction': float(user_satisfaction),
            'error_impact': float(error_penalty),
            'feedback_completeness': len([item for item in feedback_items if item.content]) / len(feedback_items)
        }

        return metrics

    def _extract_text_content(self, feedback_item: FeedbackItem) -> str:
        """Extract text content from feedback item."""
        if isinstance(feedback_item.content, dict):
            # Try different keys for text content
            for key in ['text', 'comment', 'comments', 'reason', 'explanation']:
                if key in feedback_item.content:
                    return str(feedback_item.content[key])
        elif isinstance(feedback_item.content, str):
            return feedback_item.content

        return ""

    def _classify_sentiment(self, text: str) -> str:
        """Classify sentiment of text."""
        text_lower = text.lower()
        positive_score = sum(1 for word in self.sentiment_keywords['positive'] if word in text_lower)
        negative_score = sum(1 for word in self.sentiment_keywords['negative'] if word in text_lower)

        if positive_score > negative_score:
            return 'positive'
        elif negative_score > positive_score:
            return 'negative'
        else:
            return 'neutral'

    def _detect_errors(self, text: str) -> List[str]:
        """Detect error patterns in text."""
        errors = []

        for pattern_name, pattern in [('accuracy_error', self.error_patterns[0]),
                                    ('understanding_error', self.error_patterns[1]),
                                    ('missing_info', self.error_patterns[2]),
                                    ('speed_issue', self.error_patterns[3])]:
            if pattern.search(text):
                errors.append(pattern_name)

        return errors

    def _has_errors(self, feedback_item: FeedbackItem) -> bool:
        """Check if feedback item indicates errors."""
        text_content = self._extract_text_content(feedback_item)
        return len(self._detect_errors(text_content)) > 0

    def _calculate_overall_sentiment(self, sentiment_counts: Dict[str, int]) -> str:
        """Calculate overall sentiment."""
        total = sum(sentiment_counts.values())
        if total == 0:
            return 'neutral'

        positive_ratio = sentiment_counts['positive'] / total
        negative_ratio = sentiment_counts['negative'] / total

        if positive_ratio > 0.6:
            return 'positive'
        elif negative_ratio > 0.4:
            return 'negative'
        else:
            return 'neutral'

    def _calculate_user_avg_rating(self, feedback_items: List[FeedbackItem]) -> Optional[float]:
        """Calculate average rating for a user."""
        ratings = []
        for item in feedback_items:
            if item.feedback_type == FeedbackType.RATING:
                rating = item.content.get('rating')
                if rating:
                    ratings.append(rating)

        return np.mean(ratings) if ratings else None

    def _calculate_user_positive_ratio(self, feedback_items: List[FeedbackItem]) -> float:
        """Calculate positive feedback ratio for a user."""
        positive_indicators = 0
        total_indicators = 0

        for item in feedback_items:
            if item.feedback_type == FeedbackType.RATING:
                rating = item.content.get('rating')
                if rating:
                    positive_indicators += 1 if rating >= 4 else 0
                    total_indicators += 1
            elif item.feedback_type == FeedbackType.THUMBS_UP_DOWN:
                thumbs_up = item.content.get('thumbs_up')
                if thumbs_up is not None:
                    positive_indicators += 1 if thumbs_up else 0
                    total_indicators += 1
            elif item.feedback_type == FeedbackType.TEXT_COMMENT:
                text = self._extract_text_content(item)
                if text:
                    sentiment = self._classify_sentiment(text)
                    positive_indicators += 1 if sentiment == 'positive' else 0
                    total_indicators += 1

        return positive_indicators / total_indicators if total_indicators > 0 else 0.5







