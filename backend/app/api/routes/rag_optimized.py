"""
集成优化模块到主应用
Integration of Optimization Modules into Main Application

将智能缓存和查询路由集成到 FastAPI 应用中
"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent.parent))

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import logging

from app.rag.intelligent_cache import MultiLevelCache
from app.rag.query_router import AdaptiveRAGPipeline
from app.rag.enhanced_rag_pipeline import EnhancedRAGPipeline
from app.config import settings

logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/api/v2/rag", tags=["RAG v2 (Optimized)"])


# ============================================================================
# 请求/响应模型
# ============================================================================

class OptimizedSearchRequest(BaseModel):
    """优化检索请求"""
    query: str = Field(..., description="用户查询", min_length=1, max_length=500)
    generate_answer: bool = Field(True, description="是否生成答案")
    use_cache: bool = Field(True, description="是否使用缓存")
    force_strategy: Optional[str] = Field(None, description="强制使用指定策略")


class OptimizedSearchResponse(BaseModel):
    """优化检索响应"""
    query: str
    answer: Optional[str]
    documents: List[Dict[str, Any]]
    classification: Dict[str, Any]
    from_cache: bool
    cache_level: Optional[str]
    performance: Dict[str, Any]


class CacheStatsResponse(BaseModel):
    """缓存统计响应"""
    l1: Dict[str, Any]
    l2: Dict[str, Any]
    l3: Dict[str, Any]
    overall: Dict[str, Any]


class RouterStatsResponse(BaseModel):
    """路由统计响应"""
    total_queries: int
    strategy_usage: Dict[str, int]
    strategy_distribution: Dict[str, float]


# ============================================================================
# 全局实例（单例模式）
# ============================================================================

class OptimizedRAGSystem:
    """优化的 RAG 系统（单例）"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        logger.info("初始化优化 RAG 系统...")

        # 初始化缓存
        self.cache = MultiLevelCache(
            l1_maxsize=getattr(settings, 'CACHE_L1_SIZE', 1000),
            l2_ttl=getattr(settings, 'CACHE_L2_TTL', 3600),
            l3_threshold=getattr(settings, 'CACHE_L3_THRESHOLD', 0.95),
            enable_l1=getattr(settings, 'CACHE_ENABLE_L1', True),
            enable_l2=getattr(settings, 'CACHE_ENABLE_L2', True),
            enable_l3=getattr(settings, 'CACHE_ENABLE_L3', True)
        )

        # 初始化自适应管道
        base_pipeline = EnhancedRAGPipeline(
            enable_query_rewriting=True,
            enable_observability=True,
            enable_quality_control=True
        )
        self.adaptive_pipeline = AdaptiveRAGPipeline(base_pipeline)

        self._initialized = True
        logger.info("优化 RAG 系统初始化完成")

    async def search(
        self,
        query: str,
        generate_answer: bool = True,
        use_cache: bool = True,
        force_strategy: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        智能检索

        Args:
            query: 用户查询
            generate_answer: 是否生成答案
            use_cache: 是否使用缓存
            force_strategy: 强制使用指定策略

        Returns:
            检索结果
        """
        import time
        start_time = time.time()

        # 1. 尝试缓存
        from_cache = False
        cache_level = None

        if use_cache:
            cached_result = await self.cache.get(query)
            if cached_result:
                from_cache = True
                # 判断缓存层级（简化版）
                cache_level = "L1/L2/L3"

                # 添加性能信息
                cached_result["from_cache"] = True
                cached_result["cache_level"] = cache_level
                cached_result["performance"] = {
                    "total_time_ms": round((time.time() - start_time) * 1000, 2),
                    "cache_hit": True
                }

                logger.info(f"缓存命中: {query[:50]}...")
                return cached_result

        # 2. 自适应检索
        logger.info(f"执行检索: {query[:50]}...")

        result = await self.adaptive_pipeline.search_adaptive(
            query=query,
            generate_answer=generate_answer,
            force_strategy=force_strategy
        )

        # 3. 缓存结果
        if use_cache:
            await self.cache.set(query, result)

        # 4. 添加性能信息
        result["from_cache"] = False
        result["cache_level"] = None
        result["performance"] = {
            "total_time_ms": round((time.time() - start_time) * 1000, 2),
            "cache_hit": False
        }

        return result

    async def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return await self.cache.get_stats()

    def get_router_stats(self) -> Dict[str, Any]:
        """获取路由统计"""
        return self.adaptive_pipeline.get_stats()

    async def clear_cache(self):
        """清空缓存"""
        await self.cache.clear()
        logger.info("缓存已清空")


# 全局实例
_rag_system = None


def get_rag_system() -> OptimizedRAGSystem:
    """获取 RAG 系统实例（依赖注入）"""
    global _rag_system
    if _rag_system is None:
        _rag_system = OptimizedRAGSystem()
    return _rag_system


# ============================================================================
# API 端点
# ============================================================================

@router.post("/search", response_model=OptimizedSearchResponse)
async def optimized_search(
    request: OptimizedSearchRequest,
    rag_system: OptimizedRAGSystem = Depends(get_rag_system)
):
    """
    优化检索端点

    特性：
    - 智能缓存（3 层）
    - 自适应路由（5 种查询类型）
    - 完整的 RAG Pipeline
    - 性能监控
    """
    try:
        result = await rag_system.search(
            query=request.query,
            generate_answer=request.generate_answer,
            use_cache=request.use_cache,
            force_strategy=request.force_strategy
        )

        return OptimizedSearchResponse(**result)

    except Exception as e:
        logger.error(f"检索失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"检索失败: {str(e)}")


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats(
    rag_system: OptimizedRAGSystem = Depends(get_rag_system)
):
    """
    获取缓存统计

    返回：
    - L1/L2/L3 各层命中率
    - 总体命中率
    - 缓存大小
    """
    try:
        stats = await rag_system.get_cache_stats()
        return CacheStatsResponse(**stats)

    except Exception as e:
        logger.error(f"获取缓存统计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")


@router.get("/router/stats", response_model=RouterStatsResponse)
async def get_router_stats(
    rag_system: OptimizedRAGSystem = Depends(get_rag_system)
):
    """
    获取路由统计

    返回：
    - 总查询数
    - 各策略使用次数
    - 策略分布
    """
    try:
        stats = rag_system.get_router_stats()
        return RouterStatsResponse(**stats)

    except Exception as e:
        logger.error(f"获取路由统计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")


@router.post("/cache/clear")
async def clear_cache(
    rag_system: OptimizedRAGSystem = Depends(get_rag_system)
):
    """
    清空缓存

    清空所有层级的缓存（L1/L2/L3）
    """
    try:
        await rag_system.clear_cache()
        return {"message": "缓存已清空", "success": True}

    except Exception as e:
        logger.error(f"清空缓存失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"清空缓存失败: {str(e)}")


@router.get("/health")
async def health_check(
    rag_system: OptimizedRAGSystem = Depends(get_rag_system)
):
    """
    健康检查

    检查系统各组件状态
    """
    try:
        # 检查缓存
        cache_stats = await rag_system.get_cache_stats()

        # 检查路由
        router_stats = rag_system.get_router_stats()

        return {
            "status": "healthy",
            "components": {
                "cache": {
                    "status": "ok",
                    "l1_enabled": rag_system.cache.enable_l1,
                    "l2_enabled": rag_system.cache.enable_l2,
                    "l3_enabled": rag_system.cache.enable_l3
                },
                "router": {
                    "status": "ok",
                    "total_queries": router_stats.get("total_queries", 0)
                },
                "pipeline": {
                    "status": "ok",
                    "query_rewriting": True,
                    "observability": True,
                    "quality_control": True
                }
            }
        }

    except Exception as e:
        logger.error(f"健康检查失败: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "error": str(e)
        }


# ============================================================================
# 启动事件
# ============================================================================

@router.on_event("startup")
async def startup_event():
    """应用启动时初始化"""
    logger.info("初始化优化 RAG 系统...")
    get_rag_system()
    logger.info("优化 RAG 系统已就绪")


@router.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理"""
    logger.info("关闭优化 RAG 系统...")
    # 这里可以添加清理逻辑
    logger.info("优化 RAG 系统已关闭")


# ============================================================================
# 使用示例
# ============================================================================

if __name__ == "__main__":
    """
    测试示例

    运行：
        python -m app.api.routes.rag_optimized
    """
    import asyncio

    async def test():
        # 初始化系统
        system = OptimizedRAGSystem()

        # 测试查询
        test_queries = [
            "什么是市盈率？",
            "如何计算 ROE？",
            "市盈率和市净率的区别",
        ]

        print("\n" + "="*60)
        print("测试优化 RAG 系统")
        print("="*60 + "\n")

        for query in test_queries:
            print(f"\n查询: {query}")

            # 第一次查询（无缓存）
            result1 = await system.search(query)
            print(f"  第一次: {result1['performance']['total_time_ms']}ms")
            print(f"  类型: {result1['classification']['query_type']}")
            print(f"  策略: {result1['classification']['strategy']}")

            # 第二次查询（有缓存）
            result2 = await system.search(query)
            print(f"  第二次: {result2['performance']['total_time_ms']}ms")
            print(f"  缓存命中: {result2['from_cache']}")

        # 打印统计
        print("\n" + "="*60)
        print("统计信息")
        print("="*60)

        cache_stats = await system.get_cache_stats()
        print(f"\n缓存统计:")
        print(f"  总命中率: {cache_stats['overall']['hit_rate']:.2%}")

        router_stats = system.get_router_stats()
        print(f"\n路由统计:")
        print(f"  总查询数: {router_stats['total_queries']}")
        print(f"  策略分布: {router_stats['strategy_distribution']}")

    # 运行测试
    asyncio.run(test())
