"""
Decision Engine - 决策引擎
基于分析结果生成投资参考观点
"""
from typing import Dict, Any, List


class DecisionEngine:
    """
    决策引擎
    
    职责：
    1. 综合技术面和基本面分析
    2. 生成投资参考观点
    3. 识别交易机会和风险点
    4. 提供风险提示
    
    注意：所有建议仅供参考，不构成投资建议
    """
    
    def generate_decision(
        self,
        analysis_result: Dict[str, Any],
        integrated_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        生成决策建议
        
        Args:
            analysis_result: 分析结果（来自 FastAnalyzer 或 DeepAnalyzer）
            integrated_data: 整合数据
            
        Returns:
            决策建议
        """
        if not analysis_result.get("success"):
            return {
                "success": False,
                "error": "分析结果不可用"
            }
        
        symbol_data = analysis_result.get("data", {})
        
        # 生成参考观点
        reference_view = self._generate_reference_view(symbol_data)
        
        # 识别机会和风险
        opportunities = self._identify_opportunities(symbol_data)
        risks = self._identify_risks(symbol_data)
        
        # 生成风险提示
        risk_warnings = self._generate_risk_warnings(symbol_data, risks)
        
        return {
            "success": True,
            "reference_view": reference_view,
            "opportunities": opportunities,
            "risks": risks,
            "risk_warnings": risk_warnings,
            "disclaimer": "以上内容仅供参考，不构成投资建议。投资有风险，决策需谨慎。"
        }
    
    def _generate_reference_view(self, symbol_data: Dict[str, Any]) -> Dict[str, Any]:
        """生成参考观点"""
        technical = symbol_data.get("technical", {})
        change = symbol_data.get("change", {})
        
        # 技术面评分
        tech_score = self._calculate_technical_score(technical)
        
        # 趋势评分
        trend_score = self._calculate_trend_score(change)
        
        # 综合评分
        overall_score = (tech_score + trend_score) / 2
        
        # 生成观点
        if overall_score > 0.6:
            view = "偏多"
            description = "技术面和趋势面均显示积极信号"
        elif overall_score < 0.4:
            view = "偏空"
            description = "技术面和趋势面均显示消极信号"
        else:
            view = "中性"
            description = "技术面和趋势面信号混合，建议观望"
        
        return {
            "view": view,
            "score": overall_score,
            "description": description,
            "technical_score": tech_score,
            "trend_score": trend_score
        }
    
    def _calculate_technical_score(self, technical: Dict[str, Any]) -> float:
        """计算技术面评分 (0-1)"""
        if not technical:
            return 0.5
        
        score = 0.5  # 基础分
        
        # RSI 评分
        rsi = technical.get("rsi", {})
        if rsi.get("level") == "超卖":
            score += 0.2  # 超卖是买入信号
        elif rsi.get("level") == "超买":
            score -= 0.2  # 超买是卖出信号
        
        # MACD 评分
        macd = technical.get("macd", {})
        if macd.get("signal_type") == "金叉":
            score += 0.2
        elif macd.get("signal_type") == "死叉":
            score -= 0.2
        
        # 布林带评分
        bollinger = technical.get("bollinger", {})
        if bollinger.get("position") == "下轨外":
            score += 0.1  # 超卖
        elif bollinger.get("position") == "上轨外":
            score -= 0.1  # 超买
        
        return max(0.0, min(1.0, score))
    
    def _calculate_trend_score(self, change: Dict[str, Any]) -> float:
        """计算趋势评分 (0-1)"""
        if not change:
            return 0.5
        
        change_pct = change.get("change_pct", 0)
        
        # 基于涨跌幅计算分数
        if change_pct > 10:
            return 0.9  # 强势上涨
        elif change_pct > 5:
            return 0.7  # 上涨
        elif change_pct > 2:
            return 0.6  # 微涨
        elif change_pct > -2:
            return 0.5  # 震荡
        elif change_pct > -5:
            return 0.4  # 微跌
        elif change_pct > -10:
            return 0.3  # 下跌
        else:
            return 0.1  # 强势下跌
    
    def _identify_opportunities(self, symbol_data: Dict[str, Any]) -> List[str]:
        """识别交易机会"""
        opportunities = []
        
        technical = symbol_data.get("technical", {})
        
        # RSI 超卖
        if technical.get("rsi", {}).get("level") == "超卖":
            opportunities.append("RSI超卖，可能存在反弹机会")
        
        # MACD 金叉
        if technical.get("macd", {}).get("signal_type") == "金叉":
            opportunities.append("MACD金叉，短期趋势向上")
        
        # 布林带下轨
        if technical.get("bollinger", {}).get("position") == "下轨外":
            opportunities.append("价格触及布林带下轨，可能反弹")
        
        # 趋势反转
        trend = technical.get("trend", {})
        if trend.get("direction") in ["上涨", "强势上涨"]:
            opportunities.append(f"趋势{trend.get('direction')}，动能较强")
        
        return opportunities
    
    def _identify_risks(self, symbol_data: Dict[str, Any]) -> List[str]:
        """识别风险点"""
        risks = []
        
        technical = symbol_data.get("technical", {})
        change = symbol_data.get("change", {})
        
        # RSI 超买
        if technical.get("rsi", {}).get("level") == "超买":
            risks.append("RSI超买，注意回调风险")
        
        # MACD 死叉
        if technical.get("macd", {}).get("signal_type") == "死叉":
            risks.append("MACD死叉，短期趋势向下")
        
        # 布林带上轨
        if technical.get("bollinger", {}).get("position") == "上轨外":
            risks.append("价格突破布林带上轨，可能回调")
        
        # 大幅下跌
        if change and change.get("change_pct", 0) < -5:
            risks.append(f"近期下跌{abs(change.get('change_pct'))}%，下行风险较大")
        
        # 估值风险
        info = symbol_data.get("info", {})
        pe_ratio = info.get("pe_ratio")
        if pe_ratio and pe_ratio > 50:
            risks.append(f"市盈率{pe_ratio:.1f}倍，估值偏高")
        
        return risks
    
    def _generate_risk_warnings(
        self,
        symbol_data: Dict[str, Any],
        risks: List[str]
    ) -> Dict[str, List[str]]:
        """生成风险提示"""
        return {
            "technical_risks": [r for r in risks if any(kw in r for kw in ["RSI", "MACD", "布林"])],
            "market_risks": ["市场波动风险", "流动性风险"],
            "other_risks": ["政策风险", "行业风险", "公司经营风险"]
        }
