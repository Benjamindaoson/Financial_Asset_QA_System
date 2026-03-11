"""
测试 ResponseGenerator
"""
import pytest
from app.reasoning.response_generator import ResponseGenerator


class TestResponseGenerator:
    """测试响应生成器"""

    @pytest.fixture
    def generator(self):
        """创建生成器实例"""
        return ResponseGenerator()

    @pytest.fixture
    def sample_analysis_result(self):
        """示例分析结果"""
        return {
            "success": True,
            "data": {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "price": {
                    "current": 150.25,
                    "currency": "USD",
                    "source": "yfinance"
                },
                "change": {
                    "change_pct": 2.5,
                    "trend": "上涨"
                },
                "info": {
                    "market_cap": 2500000000000,
                    "pe_ratio": 28.5
                },
                "technical": {
                    "rsi": {
                        "value": 65.0,
                        "level": "中性",
                        "signal": "持有",
                        "description": "RSI处于中性区域"
                    },
                    "macd": {
                        "macd": 1.5,
                        "signal_type": "金叉",
                        "trend": "上涨",
                        "description": "MACD金叉，看涨信号"
                    },
                    "trend": {
                        "direction": "上涨",
                        "strength": 75.0,
                        "change_pct": 2.5
                    }
                }
            }
        }

    @pytest.fixture
    def sample_decision_result(self):
        """示例决策结果"""
        return {
            "success": True,
            "reference_view": {
                "view": "偏多",
                "score": 0.7,
                "description": "技术面偏强，建议关注"
            },
            "opportunities": [
                "技术指标显示上涨趋势",
                "成交量放大"
            ],
            "risks": [
                "估值偏高",
                "市场波动加大"
            ],
            "risk_warnings": {
                "technical_risks": ["RSI接近超买区域"],
                "market_risks": ["大盘调整风险"],
                "other_risks": ["政策风险"]
            },
            "disclaimer": "以上内容仅供参考，不构成投资建议"
        }

    @pytest.fixture
    def sample_integrated_data(self):
        """示例整合数据"""
        return {
            "metadata": {
                "timestamp": "2024-01-01T00:00:00",
                "sources": ["yfinance", "alpha_vantage"]
            }
        }

    def test_generate_success(self, generator, sample_analysis_result, sample_decision_result, sample_integrated_data):
        """测试成功生成响应"""
        result = generator.generate(
            sample_analysis_result,
            sample_decision_result,
            sample_integrated_data
        )

        assert result["success"] is True
        assert "sections" in result
        assert "metadata" in result
        assert result["metadata"]["symbol"] == "AAPL"

    def test_generate_analysis_failure(self, generator, sample_decision_result, sample_integrated_data):
        """测试分析失败时的响应"""
        failed_analysis = {
            "success": False,
            "error": "分析失败"
        }

        result = generator.generate(
            failed_analysis,
            sample_decision_result,
            sample_integrated_data
        )

        assert result["success"] is False
        assert result["error"] == "分析失败"

    def test_data_summary_section(self, generator, sample_analysis_result, sample_decision_result, sample_integrated_data):
        """测试数据摘要章节"""
        result = generator.generate(
            sample_analysis_result,
            sample_decision_result,
            sample_integrated_data
        )

        data_summary = result["sections"]["data_summary"]
        assert data_summary["title"] == "📊 数据摘要"
        assert len(data_summary["items"]) > 0

        # 检查价格项
        price_item = next((item for item in data_summary["items"] if item["label"] == "当前价格"), None)
        assert price_item is not None
        assert "150.25" in price_item["value"]

    def test_technical_analysis_section(self, generator, sample_analysis_result, sample_decision_result, sample_integrated_data):
        """测试技术分析章节"""
        result = generator.generate(
            sample_analysis_result,
            sample_decision_result,
            sample_integrated_data
        )

        technical = result["sections"]["technical_analysis"]
        assert technical["title"] == "📈 技术分析"
        assert len(technical["items"]) > 0

        # 检查RSI指标
        rsi_item = next((item for item in technical["items"] if item["indicator"] == "RSI"), None)
        assert rsi_item is not None
        assert rsi_item["level"] == "中性"

    def test_reference_view_section(self, generator, sample_analysis_result, sample_decision_result, sample_integrated_data):
        """测试参考观点章节"""
        result = generator.generate(
            sample_analysis_result,
            sample_decision_result,
            sample_integrated_data
        )

        reference = result["sections"]["reference_view"]
        assert reference["title"] == "💡 参考观点"
        assert len(reference["items"]) > 0

        # 检查综合观点
        overall = next((item for item in reference["items"] if item["type"] == "overall"), None)
        assert overall is not None
        assert overall["view"] == "偏多"

    def test_risk_warnings_section(self, generator, sample_analysis_result, sample_decision_result, sample_integrated_data):
        """测试风险提示章节"""
        result = generator.generate(
            sample_analysis_result,
            sample_decision_result,
            sample_integrated_data
        )

        risk_warnings = result["sections"]["risk_warnings"]
        assert risk_warnings["title"] == "⚠️ 风险提示"
        assert len(risk_warnings["categories"]) > 0

        # 检查技术风险
        tech_risks = next((cat for cat in risk_warnings["categories"] if cat["category"] == "技术风险"), None)
        assert tech_risks is not None
        assert len(tech_risks["risks"]) > 0

    def test_empty_technical_data(self, generator, sample_decision_result, sample_integrated_data):
        """测试技术数据为空时的处理"""
        analysis_result = {
            "success": True,
            "data": {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "technical": {}
            }
        }

        result = generator.generate(
            analysis_result,
            sample_decision_result,
            sample_integrated_data
        )

        technical = result["sections"]["technical_analysis"]
        assert technical["title"] == "📈 技术分析"
        assert len(technical["items"]) == 0
        assert technical["note"] == "技术指标数据不足"

    def test_decision_failure(self, generator, sample_analysis_result, sample_integrated_data):
        """测试决策失败时的处理"""
        failed_decision = {
            "success": False
        }

        result = generator.generate(
            sample_analysis_result,
            failed_decision,
            sample_integrated_data
        )

        reference = result["sections"]["reference_view"]
        assert reference["title"] == "💡 参考观点"
        assert len(reference["items"]) == 0
        assert reference["note"] == "决策数据不可用"

    def test_type_safety_for_price_info(self, generator, sample_decision_result, sample_integrated_data):
        """测试价格信息类型安全"""
        analysis_result = {
            "success": True,
            "data": {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "price": 150.25,  # 直接是float，不是dict
                "change": "2.5%",  # 字符串，不是dict
                "info": "some info"  # 字符串，不是dict
            }
        }

        result = generator.generate(
            analysis_result,
            sample_decision_result,
            sample_integrated_data
        )

        # 应该不会抛出异常，而是优雅地处理
        assert result["success"] is True
        data_summary = result["sections"]["data_summary"]
        assert data_summary["title"] == "📊 数据摘要"

    def test_metadata_extraction(self, generator, sample_analysis_result, sample_decision_result, sample_integrated_data):
        """测试元数据提取"""
        result = generator.generate(
            sample_analysis_result,
            sample_decision_result,
            sample_integrated_data
        )

        metadata = result["metadata"]
        assert metadata["symbol"] == "AAPL"
        assert metadata["name"] == "Apple Inc."
        assert metadata["timestamp"] == "2024-01-01T00:00:00"
        assert "yfinance" in metadata["sources"]
