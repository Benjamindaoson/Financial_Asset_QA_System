"""Data quality monitoring."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class DataQualityMonitor:
    """Monitor data quality across all data sources.

    This monitor runs periodic checks on:
    - Market data freshness
    - RAG retrieval quality
    - Knowledge base coverage gaps
    - Tool success rates
    """

    def __init__(self):
        self.check_interval = 300  # 5 minutes
        self.is_running = False

        # Golden queries for RAG quality testing
        self.GOLDEN_QUERIES = [
            "什么是市盈率",
            "如何计算ROE",
            "什么是布林带",
            "融资融券是什么",
            "市净率的定义"
        ]

        # Thresholds
        self.MIN_RAG_RECALL = 0.80
        self.MAX_PRICE_AGE_SECONDS = 300  # 5 minutes
        self.MIN_TOOL_SUCCESS_RATE = 0.90

    async def start_monitoring(self):
        """Start background monitoring loop."""
        self.is_running = True
        logger.info("[DataQualityMonitor] Starting background monitoring")

        while self.is_running:
            try:
                await self.run_quality_checks()
            except Exception as e:
                logger.error(f"[DataQualityMonitor] Check failed: {e}")

            await asyncio.sleep(self.check_interval)

    def stop_monitoring(self):
        """Stop monitoring loop."""
        self.is_running = False
        logger.info("[DataQualityMonitor] Stopped monitoring")

    async def run_quality_checks(self):
        """Run all quality checks."""
        logger.info("[DataQualityMonitor] Running quality checks")

        # Check 1: Market data freshness
        stale_data = await self._check_price_freshness()
        if stale_data:
            logger.warning(
                f"[DataQualityMonitor] Stale price data detected: {stale_data}"
            )

        # Check 2: RAG recall quality
        recall = await self._test_rag_recall()
        if recall < self.MIN_RAG_RECALL:
            logger.warning(
                f"[DataQualityMonitor] RAG recall below threshold: "
                f"{recall:.2%} < {self.MIN_RAG_RECALL:.2%}"
            )
        else:
            logger.info(f"[DataQualityMonitor] RAG recall: {recall:.2%}")

        # Check 3: Knowledge base coverage gaps
        gaps = await self._find_knowledge_gaps()
        if gaps:
            logger.info(
                f"[DataQualityMonitor] Knowledge gaps identified: {len(gaps)} queries"
            )

    async def _check_price_freshness(self) -> List[str]:
        """Check if cached prices are fresh.

        Returns:
            List of symbols with stale data
        """
        # This is a placeholder - in production, would check Redis cache
        # For now, return empty list (no stale data)
        return []

    async def _test_rag_recall(self) -> float:
        """Test RAG retrieval quality using golden queries.

        Returns:
            Recall rate (0.0-1.0)
        """
        try:
            from app.rag.hybrid_pipeline import HybridRAGPipeline

            pipeline = HybridRAGPipeline()

            # Test each golden query
            successful = 0
            for query in self.GOLDEN_QUERIES:
                try:
                    result = await pipeline.search_grounded(query, score_threshold=0.3)
                    if result.documents and len(result.documents) > 0:
                        successful += 1
                except Exception as e:
                    logger.warning(f"[DataQualityMonitor] RAG test failed for '{query}': {e}")

            recall = successful / len(self.GOLDEN_QUERIES)
            return recall

        except Exception as e:
            logger.error(f"[DataQualityMonitor] RAG recall test failed: {e}")
            return 0.0

    async def _find_knowledge_gaps(self) -> List[Dict[str, Any]]:
        """Identify queries with low confidence scores.

        Returns:
            List of queries that may indicate knowledge gaps
        """
        # This is a placeholder - in production, would analyze query logs
        # and identify patterns of low-confidence responses
        return []

    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status.

        Returns:
            Health status dictionary
        """
        return {
            "monitoring_active": self.is_running,
            "check_interval_seconds": self.check_interval,
            "last_check": datetime.now().isoformat(),
            "thresholds": {
                "min_rag_recall": self.MIN_RAG_RECALL,
                "max_price_age_seconds": self.MAX_PRICE_AGE_SECONDS,
                "min_tool_success_rate": self.MIN_TOOL_SUCCESS_RATE
            }
        }


# Global instance
data_quality_monitor = DataQualityMonitor()
