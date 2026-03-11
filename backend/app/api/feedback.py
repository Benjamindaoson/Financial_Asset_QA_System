"""
用户反馈 API 路由
User Feedback API Routes
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class FeedbackRequest(BaseModel):
    """反馈请求模型"""
    message_id: str
    rating: str  # "positive" or "negative"
    timestamp: str
    comment: Optional[str] = None


# 简单的内存存储（生产环境应使用数据库）
feedback_storage = []


@router.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    """提交用户反馈"""
    feedback_entry = {
        "message_id": request.message_id,
        "rating": request.rating,
        "timestamp": request.timestamp,
        "comment": request.comment,
        "received_at": datetime.utcnow().isoformat(),
    }

    feedback_storage.append(feedback_entry)

    return {
        "success": True,
        "message": "Feedback received",
        "feedback_id": len(feedback_storage),
    }


@router.get("/feedback/stats")
async def get_feedback_stats():
    """获取反馈统计"""
    if not feedback_storage:
        return {
            "total": 0,
            "positive": 0,
            "negative": 0,
            "positive_rate": 0.0,
        }

    total = len(feedback_storage)
    positive = sum(1 for f in feedback_storage if f["rating"] == "positive")
    negative = sum(1 for f in feedback_storage if f["rating"] == "negative")

    return {
        "total": total,
        "positive": positive,
        "negative": negative,
        "positive_rate": positive / total if total > 0 else 0.0,
    }
