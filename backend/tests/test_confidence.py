"""
测试置信度评分器
"""
import pytest
from app.rag.confidence import ConfidenceScorer
from app.models.schemas import Document


class TestConfidenceScorerInitialization:
    """测试置信度评分器初始化"""

    def test_scorer_initialization(self):
        """测试评分器初始化"""
        scorer = ConfidenceScorer()

        assert scorer is not None
        assert scorer.weights is not None
        assert 'retrieval' in scorer.weights
        assert 'gap' in scorer.weights
        assert 'coverage' in scorer.weights


class TestConfidenceCalculation:
    """测试置信度计算"""

    @pytest.fixture
    def scorer(self):
        """创建评分器实例"""
        return ConfidenceScorer()

    def test_calculate_with_no_documents(self, scorer):
        """测试无文档情况"""
        confidence = scorer.calculate("测试查询", [])

        assert confidence == 0.0

    def test_calculate_with_single_document(self, scorer):
        """测试单个文档"""
        documents = [
            Document(
                content="市盈率是衡量股票估值的重要指标",
                source="test",
                score=0.9
            )
        ]

        confidence = scorer.calculate("什么是市盈率", documents)

        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0

    def test_calculate_with_multiple_documents(self, scorer):
        """测试多个文档"""
        documents = [
            Document(
                content="市盈率是衡量股票估值的重要指标",
                source="test",
                score=0.9
            ),
            Document(
                content="市盈率计算公式是股价除以每股收益",
                source="test",
                score=0.7
            )
        ]

        confidence = scorer.calculate("什么是市盈率", documents)

        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0

    def test_calculate_with_high_score_gap(self, scorer):
        """测试高分差距"""
        documents = [
            Document(
                content="市盈率是衡量股票估值的重要指标",
                source="test",
                score=0.95
            ),
            Document(
                content="其他内容",
                source="test",
                score=0.5
            )
        ]

        confidence = scorer.calculate("什么是市盈率", documents)

        # 高分差距应该提高置信度
        assert confidence > 0.5


class TestCoverageCalculation:
    """测试覆盖度计算"""

    @pytest.fixture
    def scorer(self):
        """创建评分器实例"""
        return ConfidenceScorer()

    def test_coverage_full_match(self, scorer):
        """测试完全匹配"""
        query = "市盈率"
        document = "市盈率是重要指标"

        coverage = scorer._calculate_coverage(query, document)

        assert coverage > 0.0

    def test_coverage_partial_match(self, scorer):
        """测试部分匹配"""
        query = "市盈率和市净率"
        document = "市盈率是重要指标"

        coverage = scorer._calculate_coverage(query, document)

        assert 0.0 < coverage < 1.0

    def test_coverage_no_match(self, scorer):
        """测试无匹配"""
        query = "市盈率"
        document = "完全不相关的内容"

        coverage = scorer._calculate_coverage(query, document)

        assert coverage >= 0.0

    def test_coverage_with_stopwords(self, scorer):
        """测试包含停用词"""
        query = "什么是市盈率"
        document = "市盈率是重要指标"

        coverage = scorer._calculate_coverage(query, document)

        # 停用词应该被过滤
        assert coverage > 0.0


class TestConfidenceLevel:
    """测试置信度等级"""

    @pytest.fixture
    def scorer(self):
        """创建评分器实例"""
        return ConfidenceScorer()

    def test_high_confidence(self, scorer):
        """测试高置信度"""
        level = scorer.get_confidence_level(0.85)

        assert level == "高"

    def test_medium_confidence(self, scorer):
        """测试中等置信度"""
        level = scorer.get_confidence_level(0.65)

        assert level == "中"

    def test_low_confidence(self, scorer):
        """测试低置信度"""
        level = scorer.get_confidence_level(0.45)

        assert level == "低"

    def test_very_low_confidence(self, scorer):
        """测试极低置信度"""
        level = scorer.get_confidence_level(0.25)

        assert level == "极低"

    def test_boundary_high(self, scorer):
        """测试高置信度边界"""
        level = scorer.get_confidence_level(0.8)

        assert level == "高"

    def test_boundary_medium(self, scorer):
        """测试中等置信度边界"""
        level = scorer.get_confidence_level(0.6)

        assert level == "中"

    def test_boundary_low(self, scorer):
        """测试低置信度边界"""
        level = scorer.get_confidence_level(0.4)

        assert level == "低"


class TestShouldAnswer:
    """测试是否应该回答"""

    @pytest.fixture
    def scorer(self):
        """创建评分器实例"""
        return ConfidenceScorer()

    def test_should_answer_high_confidence(self, scorer):
        """测试高置信度应该回答"""
        should = scorer.should_answer(0.8)

        assert should is True

    def test_should_answer_low_confidence(self, scorer):
        """测试低置信度不应该回答"""
        should = scorer.should_answer(0.2)

        assert should is False

    def test_should_answer_at_threshold(self, scorer):
        """测试阈值边界"""
        should = scorer.should_answer(0.4, threshold=0.4)

        assert should is True

    def test_should_answer_custom_threshold(self, scorer):
        """测试自定义阈值"""
        should = scorer.should_answer(0.5, threshold=0.6)

        assert should is False
