"""
智能格式化器 - 自动选择最佳展示格式
Smart Formatter with Automatic Format Selection
"""
from typing import Dict, List, Any, Optional
from enum import Enum


class DataType(str, Enum):
    """数据类型"""
    COMPARISON = "comparison"  # 对比类
    TREND = "trend"  # 趋势类
    STEPS = "steps"  # 步骤类
    FEATURES = "features"  # 特征类
    METRICS = "metrics"  # 指标类
    PARAGRAPH = "paragraph"  # 段落类


class SmartFormatter:
    """智能格式化器"""

    def format_answer(self, query: str, data: Dict) -> Dict:
        """
        智能格式化答案

        Args:
            query: 用户查询
            data: 数据

        Returns:
            格式化后的结构化数据
        """
        # 1. 分析数据类型
        data_type = self.analyze_data_type(query, data)

        # 2. 选择最佳格式
        if data_type == DataType.COMPARISON:
            return self.format_as_table(data)
        elif data_type == DataType.TREND:
            return self.format_as_chart(data)
        elif data_type == DataType.STEPS:
            return self.format_as_ordered_list(data)
        elif data_type == DataType.FEATURES:
            return self.format_as_bullet_list(data)
        elif data_type == DataType.METRICS:
            return self.format_as_metrics_card(data)
        else:
            return self.format_as_paragraph(data)

    def analyze_data_type(self, query: str, data: Dict) -> DataType:
        """
        分析数据类型

        Args:
            query: 用户查询
            data: 数据

        Returns:
            数据类型
        """
        query_lower = query.lower()

        # 对比类
        if any(kw in query_lower for kw in ["对比", "比较", "区别", "vs"]):
            return DataType.COMPARISON

        # 趋势类
        if any(kw in query_lower for kw in ["趋势", "走势", "变化", "历史"]):
            return DataType.TREND

        # 步骤类
        if any(kw in query_lower for kw in ["如何", "怎么", "步骤", "方法"]):
            return DataType.STEPS

        # 特征类
        if any(kw in query_lower for kw in ["特点", "特征", "优势", "缺点"]):
            return DataType.FEATURES

        # 指标类
        if "price_change" in data or "volume_analysis" in data:
            return DataType.METRICS

        # 默认段落
        return DataType.PARAGRAPH

    def format_as_table(self, data: Dict) -> Dict:
        """格式化为表格"""
        return {
            "type": "table",
            "data": {
                "headers": self._extract_headers(data),
                "rows": self._extract_rows(data),
            },
            "caption": "对比数据",
        }

    def format_as_chart(self, data: Dict) -> Dict:
        """格式化为图表"""
        return {
            "type": "chart",
            "chart_type": "line",
            "data": {
                "labels": self._extract_labels(data),
                "datasets": self._extract_datasets(data),
            },
            "options": {
                "title": "趋势图",
                "xAxis": "时间",
                "yAxis": "价格",
            },
        }

    def format_as_ordered_list(self, data: Dict) -> Dict:
        """格式化为有序列表"""
        steps = self._extract_steps(data)
        return {
            "type": "ordered_list",
            "items": steps,
            "title": "操作步骤",
        }

    def format_as_bullet_list(self, data: Dict) -> Dict:
        """格式化为无序列表"""
        features = self._extract_features(data)
        return {
            "type": "bullet_list",
            "items": features,
            "title": "要点总结",
        }

    def format_as_metrics_card(self, data: Dict) -> Dict:
        """格式化为指标卡片"""
        return {
            "type": "metrics_card",
            "metrics": [
                {
                    "label": "当前价格",
                    "value": data.get("price", "N/A"),
                    "unit": data.get("currency", "USD"),
                    "trend": self._calculate_trend(data),
                },
                {
                    "label": "涨跌幅",
                    "value": data.get("change_percent", "N/A"),
                    "unit": "%",
                    "trend": "up" if data.get("change_percent", 0) > 0 else "down",
                },
                {
                    "label": "成交量",
                    "value": data.get("volume", "N/A"),
                    "unit": "",
                    "trend": "neutral",
                },
            ],
        }

    def format_as_paragraph(self, data: Dict) -> Dict:
        """格式化为段落"""
        return {
            "type": "paragraph",
            "content": self._extract_text(data),
        }

    def _extract_headers(self, data: Dict) -> List[str]:
        """提取表格表头"""
        # 简化实现
        return ["指标", "数值"]

    def _extract_rows(self, data: Dict) -> List[List[str]]:
        """提取表格行"""
        rows = []
        for key, value in data.items():
            if isinstance(value, (int, float, str)):
                rows.append([key, str(value)])
        return rows

    def _extract_labels(self, data: Dict) -> List[str]:
        """提取图表标签"""
        if "data" in data and isinstance(data["data"], list):
            return [str(i) for i in range(len(data["data"]))]
        return []

    def _extract_datasets(self, data: Dict) -> List[Dict]:
        """提取图表数据集"""
        if "data" in data and isinstance(data["data"], list):
            return [{
                "label": "价格",
                "data": [d.get("close", 0) for d in data["data"]],
            }]
        return []

    def _extract_steps(self, data: Dict) -> List[str]:
        """提取步骤"""
        # 简化实现
        if isinstance(data, dict) and "steps" in data:
            return data["steps"]
        return ["步骤1", "步骤2", "步骤3"]

    def _extract_features(self, data: Dict) -> List[str]:
        """提取特征"""
        features = []
        for key, value in data.items():
            if isinstance(value, str):
                features.append(f"{key}: {value}")
        return features

    def _calculate_trend(self, data: Dict) -> str:
        """计算趋势"""
        change = data.get("change_percent", 0)
        if change > 0:
            return "up"
        elif change < 0:
            return "down"
        else:
            return "neutral"

    def _extract_text(self, data: Dict) -> str:
        """提取文本内容"""
        if isinstance(data, str):
            return data
        elif isinstance(data, dict):
            if "answer" in data:
                return data["answer"]
            elif "content" in data:
                return data["content"]
        return str(data)
