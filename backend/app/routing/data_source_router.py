"""
智能数据源路由器
根据查询类型选择最合适的 API 组合
"""
from typing import Dict, List, Set
from enum import Enum


class DataSource(str, Enum):
    """数据源枚举"""
    YFINANCE = "yfinance"
    FINNHUB = "finnhub"
    TWELVEDATA = "twelvedata"
    NEWSAPI = "newsapi"


class QueryCategory(str, Enum):
    """查询类别"""
    PRICE = "price"              # 价格查询
    HISTORY = "history"          # 历史走势
    NEWS = "news"                # 新闻查询
    TECHNICAL = "technical"      # 技术分析
    FUNDAMENTAL = "fundamental"  # 基本面
    COMPREHENSIVE = "comprehensive"  # 综合分析


class DataSourceRouter:
    """数据源智能路由器"""

    def __init__(self):
        # 定义每种查询类型的数据源策略
        self.strategies = {
            QueryCategory.PRICE: {
                "primary": [DataSource.YFINANCE, DataSource.FINNHUB],
                "news": [],
                "technical": [],
                "priority": "speed"  # 优先速度
            },
            QueryCategory.HISTORY: {
                "primary": [DataSource.YFINANCE],
                "news": [],
                "technical": [DataSource.TWELVEDATA],  # 可选技术指标
                "priority": "accuracy"  # 优先准确性
            },
            QueryCategory.NEWS: {
                "primary": [DataSource.YFINANCE],  # 基础数据
                "news": [DataSource.FINNHUB, DataSource.NEWSAPI],  # 并行新闻
                "technical": [],
                "priority": "coverage"  # 优先覆盖面
            },
            QueryCategory.TECHNICAL: {
                "primary": [DataSource.YFINANCE],
                "news": [],
                "technical": [DataSource.TWELVEDATA],  # 技术指标
                "priority": "accuracy"
            },
            QueryCategory.FUNDAMENTAL: {
                "primary": [DataSource.YFINANCE, DataSource.FINNHUB],
                "news": [],
                "technical": [],
                "priority": "completeness"  # 优先完整性
            },
            QueryCategory.COMPREHENSIVE: {
                "primary": [DataSource.YFINANCE, DataSource.FINNHUB],
                "news": [DataSource.FINNHUB, DataSource.NEWSAPI],
                "technical": [DataSource.TWELVEDATA],
                "priority": "completeness"
            }
        }

    def route(self, category: QueryCategory) -> Dict[str, List[DataSource]]:
        """
        根据查询类别返回数据源策略

        Returns:
            {
                "primary": [主要数据源],
                "news": [新闻数据源],
                "technical": [技术指标数据源],
                "priority": "优先级策略"
            }
        """
        return self.strategies.get(category, self.strategies[QueryCategory.COMPREHENSIVE])

    def get_fallback_sources(self, primary_source: DataSource) -> List[DataSource]:
        """
        获取降级数据源

        Args:
            primary_source: 主数据源

        Returns:
            降级数据源列表
        """
        fallback_map = {
            DataSource.YFINANCE: [DataSource.FINNHUB, DataSource.TWELVEDATA],
            DataSource.FINNHUB: [DataSource.YFINANCE, DataSource.TWELVEDATA],
            DataSource.TWELVEDATA: [DataSource.YFINANCE, DataSource.FINNHUB],
        }
        return fallback_map.get(primary_source, [])

    def should_use_technical_indicators(self, category: QueryCategory) -> bool:
        """判断是否需要技术指标"""
        return category in [QueryCategory.TECHNICAL, QueryCategory.COMPREHENSIVE]

    def should_fetch_news(self, category: QueryCategory) -> bool:
        """判断是否需要获取新闻"""
        return category in [QueryCategory.NEWS, QueryCategory.COMPREHENSIVE]

    def get_parallel_sources(self, category: QueryCategory) -> Set[DataSource]:
        """
        获取可以并行调用的所有数据源

        Returns:
            所有需要调用的数据源集合
        """
        strategy = self.route(category)
        sources = set()
        sources.update(strategy["primary"])
        sources.update(strategy["news"])
        sources.update(strategy["technical"])
        return sources

    def explain_strategy(self, category: QueryCategory) -> str:
        """解释选择的策略"""
        strategy = self.route(category)

        explanation = f"查询类型: {category.value}\n"
        explanation += f"优先级: {strategy['priority']}\n"
        explanation += f"主要数据源: {', '.join([s.value for s in strategy['primary']])}\n"

        if strategy['news']:
            explanation += f"新闻来源: {', '.join([s.value for s in strategy['news']])}\n"

        if strategy['technical']:
            explanation += f"技术指标: {', '.join([s.value for s in strategy['technical']])}\n"

        return explanation


# 使用示例
if __name__ == "__main__":
    router = DataSourceRouter()

    print("=== 价格查询策略 ===")
    print(router.explain_strategy(QueryCategory.PRICE))

    print("\n=== 新闻查询策略 ===")
    print(router.explain_strategy(QueryCategory.NEWS))

    print("\n=== 综合分析策略 ===")
    print(router.explain_strategy(QueryCategory.COMPREHENSIVE))

    print("\n=== 并行数据源 ===")
    sources = router.get_parallel_sources(QueryCategory.COMPREHENSIVE)
    print(f"需要并行调用: {', '.join([s.value for s in sources])}")
