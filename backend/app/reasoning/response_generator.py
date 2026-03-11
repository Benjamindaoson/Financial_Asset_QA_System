"""
Response Generator - 响应生成器
将分析结果转换为结构化的用户响应
"""
from typing import Dict, Any, List


class ResponseGenerator:
    """
    响应生成器
    
    职责：
    1. 将分析结果格式化为结构化响应
    2. 生成符合 System Prompt 要求的输出
    3. 确保响应包含所有必要章节
    """
    
    def generate(
        self,
        analysis_result: Dict[str, Any],
        decision_result: Dict[str, Any],
        integrated_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        生成结构化响应
        
        Args:
            analysis_result: 分析结果
            decision_result: 决策结果
            integrated_data: 整合数据
            
        Returns:
            结构化响应
        """
        if not analysis_result.get("success"):
            return {
                "success": False,
                "error": analysis_result.get("error", "分析失败")
            }
        
        # 提取数据
        symbol_data = analysis_result.get("data", {})
        
        # 生成各个章节
        data_summary = self._generate_data_summary(symbol_data)
        technical_analysis = self._generate_technical_analysis(symbol_data)
        reference_view = self._generate_reference_view(decision_result)
        risk_warnings = self._generate_risk_warnings(decision_result)
        
        return {
            "success": True,
            "sections": {
                "data_summary": data_summary,
                "technical_analysis": technical_analysis,
                "reference_view": reference_view,
                "risk_warnings": risk_warnings
            },
            "metadata": {
                "symbol": symbol_data.get("symbol"),
                "name": symbol_data.get("name"),
                "timestamp": integrated_data.get("metadata", {}).get("timestamp"),
                "sources": integrated_data.get("metadata", {}).get("sources", [])
            }
        }
    
    def _generate_data_summary(self, symbol_data: Dict[str, Any]) -> Dict[str, Any]:
        """生成数据摘要章节"""
        price_info = symbol_data.get("price", {})
        change_info = symbol_data.get("change", {})
        info = symbol_data.get("info", {})

        # 确保 price_info 是字典
        if not isinstance(price_info, dict):
            price_info = {}
        if not isinstance(change_info, dict):
            change_info = {}
        if not isinstance(info, dict):
            info = {}

        items = []

        # 当前价格
        if price_info.get("current"):
            items.append({
                "label": "当前价格",
                "value": f"{price_info.get('current')} {price_info.get('currency', 'USD')}",
                "source": price_info.get("source")
            })

        # 涨跌幅
        if change_info:
            change_pct = change_info.get("change_pct", 0)
            sign = "+" if change_pct > 0 else ""
            items.append({
                "label": "涨跌幅",
                "value": f"{sign}{change_pct:.2f}%",
                "trend": change_info.get("trend")
            })

        # 市值
        if info.get("market_cap"):
            market_cap_b = info.get("market_cap") / 1e9
            items.append({
                "label": "市值",
                "value": f"{market_cap_b:.2f}B USD"
            })

        # 市盈率
        if info.get("pe_ratio"):
            items.append({
                "label": "市盈率",
                "value": f"{info.get('pe_ratio'):.2f}"
            })

        return {
            "title": "📊 数据摘要",
            "items": items
        }
    
    def _generate_technical_analysis(self, symbol_data: Dict[str, Any]) -> Dict[str, Any]:
        """生成技术分析章节"""
        technical = symbol_data.get("technical", {})
        
        if not technical:
            return {
                "title": "📈 技术分析",
                "items": [],
                "note": "技术指标数据不足"
            }
        
        items = []
        
        # RSI
        rsi = technical.get("rsi", )
        if rsi:
            items.append({
                "indicator": "RSI",
                "value": f"{rsi.get('value', 0):.1f}",
                "level": rsi.get("level"),
                "signal": rsi.get("signal"),
                "description": rsi.get("description")
            })
        
        # MACD
        macd = technical.get("macd", {})
        if macd:
            items.append({
                "indicator": "MACD",
                "value": f"{macd.get('macd', 0):.2f}",
                "signal_type": macd.get("signal_type"),
                "trend": macd.get("trend"),
                "description": macd.get("description")
            })
        
        # 趋势
        trend = technical.get("trend", {})
        if trend:
            items.append({
                "indicator": "趋势",
                "direction": trend.get("direction"),
                "strength": f"{trend.get('strength', 0):.1f}%",
                "change_pct": f"{trend.get('change_pct', 0):.2f}%"
            })
        
        return {
            "title": "📈 技术分析",
            "items": items
        }
    
    def _generate_reference_view(self, decision_result: Dict[str, Any]) -> Dict[str, Any]:
        """生成参考观点章节"""
        if not decision_result.get("success"):
            return {
                "title": "💡 参考观点",
                "items": [],
                "note": "决策数据不可用"
            }
        
        reference = decision_result.get("reference_view", {})
        opportunities = decision_result.get("opportunities", [])
        risks = decision_result.get("risks", [])
        
        items = []
        
        # 综合观点
        items.append({
            "type": "overall",
            "view": reference.get("view"),
            "score": reference.get("score"),
            "description": reference.get("description")
        })
        
        # 交易机会
        if opportunities:
            items.append({
                "type": "opportunities",
                "title": "可能的交易机会",
                "points": opportunities
            })
        
        # 风险点
        if risks:
            items.append({
                "type": "risks",
                "title": "需要关注的风险",
                "points": risks
            })
        
        return {
            "title": "💡 参考观点",
            "items": items,
            "disclaimer": decision_result.get("disclaimer")
        }
    
    def _generate_risk_warnings(self, decision_result: Dict[str, Any]) -> Dict[str, Any]:
        """生成风险提示章节"""
        if not decision_result.get("success"):
            return {
                "title": "⚠️ 风险提示",
                "categories": []
            }
        
        risk_warnings = decision_result.get("risk_warnings", {})
        
        categories = []
        
        # 技术风险
        tech_risks = risk_warnings.get("technical_risks", [])
        if tech_risks:
            categories.append({
                "category": "技术风险",
                "risks": tech_risks
            })
        
        # 市场风险
        market_risks = risk_warnings.get("market_risks", [])
        if market_risks:
            categories.append({
                "category": "市场风险",
                "risks": market_risks
            })
        
        # 其他风险
        other_risks = risk_warnings.get("other_risks", [])
        if other_risks:
            categories.append({
                "category": "其他风险",
                "risks": other_risks
            })
        
        return {
            "title": "⚠️ 风险提示",
            "categories": categories
        }
