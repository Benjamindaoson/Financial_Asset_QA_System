"""Test data quality monitoring."""

import pytest
from app.observability.data_quality import DataQualityMonitor


class TestDataQualityMonitor:
    """Test suite for DataQualityMonitor."""

    @pytest.fixture
    def monitor(self):
        """Create DataQualityMonitor instance."""
        return DataQualityMonitor()

    def test_monitor_initialization(self, monitor):
        """Test monitor initialization."""
        assert monitor.check_interval == 300
        assert monitor.is_running is False
        assert len(monitor.GOLDEN_QUERIES) > 0

    def test_get_health_status(self, monitor):
        """Test getting health status."""
        status = monitor.get_health_status()

        assert "monitoring_active" in status
        assert "check_interval_seconds" in status
        assert "thresholds" in status
        assert status["thresholds"]["min_rag_recall"] == 0.80

    @pytest.mark.asyncio
    async def test_check_price_freshness(self, monitor):
        """Test price freshness check."""
        stale_data = await monitor._check_price_freshness()

        # Should return list (empty in test environment)
        assert isinstance(stale_data, list)

    @pytest.mark.asyncio
    async def test_rag_recall_test(self, monitor):
        """Test RAG recall testing."""
        recall = await monitor._test_rag_recall()

        # Should return float between 0 and 1
        assert isinstance(recall, float)
        assert 0.0 <= recall <= 1.0

    @pytest.mark.asyncio
    async def test_find_knowledge_gaps(self, monitor):
        """Test knowledge gap identification."""
        gaps = await monitor._find_knowledge_gaps()

        # Should return list
        assert isinstance(gaps, list)

    @pytest.mark.asyncio
    async def test_run_quality_checks(self, monitor):
        """Test running all quality checks."""
        # Should not raise exception
        await monitor.run_quality_checks()

    def test_stop_monitoring(self, monitor):
        """Test stopping monitoring."""
        monitor.is_running = True
        monitor.stop_monitoring()

        assert monitor.is_running is False
