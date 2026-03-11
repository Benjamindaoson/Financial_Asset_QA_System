"""
性能监控 API - Performance Monitoring API
提供系统性能指标、健康检查和统计数据
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import time
import psutil
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class PerformanceMetrics(BaseModel):
    """性能指标模型"""
    timestamp: str
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_percent: float
    response_times: Dict[str, float]
    request_count: int
    error_count: int
    uptime_seconds: float


class HealthStatus(BaseModel):
    """健康状态模型"""
    status: str
    timestamp: str
    components: Dict[str, str]
    metrics: Dict[str, float]


# 全局性能统计
performance_stats = {
    "start_time": time.time(),
    "request_count": 0,
    "error_count": 0,
    "response_times": [],
    "endpoint_stats": {},
}


def record_request(endpoint: str, response_time: float, success: bool = True):
    """记录请求统计"""
    performance_stats["request_count"] += 1
    if not success:
        performance_stats["error_count"] += 1

    performance_stats["response_times"].append(response_time)
    if len(performance_stats["response_times"]) > 1000:
        performance_stats["response_times"] = performance_stats["response_times"][-1000:]

    if endpoint not in performance_stats["endpoint_stats"]:
        performance_stats["endpoint_stats"][endpoint] = {
            "count": 0,
            "total_time": 0,
            "errors": 0,
        }

    stats = performance_stats["endpoint_stats"][endpoint]
    stats["count"] += 1
    stats["total_time"] += response_time
    if not success:
        stats["errors"] += 1


@router.get("/metrics", response_model=PerformanceMetrics)
async def get_metrics():
    """获取系统性能指标"""
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    response_times = performance_stats["response_times"]
    avg_response_time = sum(response_times) / len(response_times) if response_times else 0
    p50_response_time = sorted(response_times)[len(response_times) // 2] if response_times else 0
    p95_response_time = sorted(response_times)[int(len(response_times) * 0.95)] if response_times else 0

    uptime = time.time() - performance_stats["start_time"]

    return PerformanceMetrics(
        timestamp=datetime.utcnow().isoformat(),
        cpu_percent=cpu_percent,
        memory_percent=memory.percent,
        memory_used_mb=memory.used / (1024 * 1024),
        memory_total_mb=memory.total / (1024 * 1024),
        disk_percent=disk.percent,
        response_times={
            "avg": round(avg_response_time, 3),
            "p50": round(p50_response_time, 3),
            "p95": round(p95_response_time, 3),
        },
        request_count=performance_stats["request_count"],
        error_count=performance_stats["error_count"],
        uptime_seconds=round(uptime, 2),
    )


@router.get("/health/detailed", response_model=HealthStatus)
async def get_detailed_health():
    """获取详细健康状态"""
    try:
        from app.rag.pipeline import RAGPipeline
        rag_pipeline = RAGPipeline()
        rag_status = "healthy" if len(rag_pipeline.source_documents) > 0 else "degraded"
        rag_docs = len(rag_pipeline.source_documents)
        rag_chunks = len(rag_pipeline.knowledge_chunks)
    except Exception:
        rag_status = "unhealthy"
        rag_docs = 0
        rag_chunks = 0

    try:
        from app.config import settings
        llm_status = "healthy" if settings.DEEPSEEK_API_KEY else "degraded"
    except Exception:
        llm_status = "unhealthy"

    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()

    overall_status = "healthy"
    if rag_status == "unhealthy" or llm_status == "unhealthy":
        overall_status = "unhealthy"
    elif rag_status == "degraded" or llm_status == "degraded":
        overall_status = "degraded"

    if cpu_percent > 90 or memory.percent > 90:
        overall_status = "degraded"

    return HealthStatus(
        status=overall_status,
        timestamp=datetime.utcnow().isoformat(),
        components={
            "rag_pipeline": rag_status,
            "llm_service": llm_status,
            "system": "healthy" if cpu_percent < 90 and memory.percent < 90 else "degraded",
        },
        metrics={
            "rag_documents": rag_docs,
            "rag_chunks": rag_chunks,
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "uptime_seconds": time.time() - performance_stats["start_time"],
        },
    )


@router.get("/stats/endpoints")
async def get_endpoint_stats():
    """获取各端点统计信息"""
    stats = []
    for endpoint, data in performance_stats["endpoint_stats"].items():
        avg_time = data["total_time"] / data["count"] if data["count"] > 0 else 0
        error_rate = data["errors"] / data["count"] if data["count"] > 0 else 0

        stats.append({
            "endpoint": endpoint,
            "request_count": data["count"],
            "avg_response_time": round(avg_time, 3),
            "error_count": data["errors"],
            "error_rate": round(error_rate * 100, 2),
        })

    return {
        "endpoints": sorted(stats, key=lambda x: x["request_count"], reverse=True),
        "total_requests": performance_stats["request_count"],
        "total_errors": performance_stats["error_count"],
    }


@router.post("/stats/reset")
async def reset_stats():
    """重置统计数据"""
    performance_stats["request_count"] = 0
    performance_stats["error_count"] = 0
    performance_stats["response_times"] = []
    performance_stats["endpoint_stats"] = {}
    performance_stats["start_time"] = time.time()

    return {"success": True, "message": "Statistics reset successfully"}
