"""Tests for confidence scoring."""

import pytest

from app.models.schemas import Document
from app.rag.confidence import ConfidenceScorer


class TestConfidenceScorerInitialization:
    def test_scorer_initialization(self):
        scorer = ConfidenceScorer()

        assert scorer is not None
        assert scorer.weights is not None
        assert "retrieval" in scorer.weights
        assert "gap" in scorer.weights
        assert "coverage" in scorer.weights
        assert "support" in scorer.weights


class TestConfidenceCalculation:
    @pytest.fixture
    def scorer(self):
        return ConfidenceScorer()

    def test_calculate_with_no_documents(self, scorer):
        confidence = scorer.calculate("测试查询", [])
        assert confidence == 0.0

    def test_calculate_with_single_document(self, scorer):
        documents = [Document(content="市盈率是衡量股票估值的重要指标。", source="test", score=0.9)]
        confidence = scorer.calculate("什么是市盈率", documents)

        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0

    def test_calculate_with_multiple_documents(self, scorer):
        documents = [
            Document(content="市盈率是衡量股票估值的重要指标。", source="valuation", score=0.9),
            Document(content="市盈率计算公式是股价除以每股收益。", source="valuation", score=0.7),
        ]
        confidence = scorer.calculate("什么是市盈率", documents)

        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0

    def test_calculate_with_high_score_gap(self, scorer):
        documents = [
            Document(content="市盈率是衡量股票估值的重要指标。", source="valuation", score=0.95),
            Document(content="其他内容", source="misc", score=0.5),
        ]
        confidence = scorer.calculate("什么是市盈率", documents)
        assert confidence > 0.5


class TestCoverageCalculation:
    @pytest.fixture
    def scorer(self):
        return ConfidenceScorer()

    def test_coverage_full_match(self, scorer):
        coverage = scorer._calculate_coverage("市盈率", "市盈率是重要指标")
        assert coverage > 0.0

    def test_coverage_partial_match(self, scorer):
        coverage = scorer._calculate_coverage("市盈率和市净率", "市盈率是重要指标")
        assert 0.0 < coverage < 1.0

    def test_coverage_no_match(self, scorer):
        coverage = scorer._calculate_coverage("市盈率", "完全不相关的内容")
        assert coverage >= 0.0

    def test_coverage_with_stopwords(self, scorer):
        coverage = scorer._calculate_coverage("什么是市盈率", "市盈率是重要指标")
        assert coverage > 0.0


class TestConfidenceLevel:
    @pytest.fixture
    def scorer(self):
        return ConfidenceScorer()

    def test_high_confidence(self, scorer):
        assert scorer.get_confidence_level(0.85) == "高"

    def test_medium_confidence(self, scorer):
        assert scorer.get_confidence_level(0.65) == "中"

    def test_low_confidence(self, scorer):
        assert scorer.get_confidence_level(0.45) == "低"

    def test_very_low_confidence(self, scorer):
        assert scorer.get_confidence_level(0.25) == "极低"

    def test_boundary_high(self, scorer):
        assert scorer.get_confidence_level(0.8) == "高"

    def test_boundary_medium(self, scorer):
        assert scorer.get_confidence_level(0.6) == "中"

    def test_boundary_low(self, scorer):
        assert scorer.get_confidence_level(0.4) == "低"


class TestShouldAnswer:
    @pytest.fixture
    def scorer(self):
        return ConfidenceScorer()

    def test_should_answer_high_confidence(self, scorer):
        assert scorer.should_answer(0.8) is True

    def test_should_answer_low_confidence(self, scorer):
        assert scorer.should_answer(0.2) is False

    def test_should_answer_at_threshold(self, scorer):
        assert scorer.should_answer(0.4, threshold=0.4) is True

    def test_should_answer_custom_threshold(self, scorer):
        assert scorer.should_answer(0.5, threshold=0.6) is False
