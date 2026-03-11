"""
多轮对话会话管理 - Multi-turn Conversation Session Management
支持会话历史、上下文管理和会话持久化
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class Message(BaseModel):
    """消息模型"""
    role: str  # "user" or "assistant"
    content: str
    timestamp: str
    metadata: Optional[Dict] = None


class Session(BaseModel):
    """会话模型"""
    session_id: str
    created_at: str
    updated_at: str
    messages: List[Message]
    context: Dict
    active: bool


class SessionCreateRequest(BaseModel):
    """创建会话请求"""
    initial_context: Optional[Dict] = None


class SessionUpdateRequest(BaseModel):
    """更新会话请求"""
    context: Optional[Dict] = None


class MessageAddRequest(BaseModel):
    """添加消息请求"""
    role: str
    content: str
    metadata: Optional[Dict] = None


# 会话存储（生产环境应使用 Redis 或数据库）
sessions_storage: Dict[str, Session] = {}

# 会话过期时间（小时）
SESSION_EXPIRE_HOURS = 24


def cleanup_expired_sessions():
    """清理过期会话"""
    now = datetime.utcnow()
    expired_sessions = []

    for session_id, session in sessions_storage.items():
        updated_at = datetime.fromisoformat(session.updated_at)
        if now - updated_at > timedelta(hours=SESSION_EXPIRE_HOURS):
            expired_sessions.append(session_id)

    for session_id in expired_sessions:
        del sessions_storage[session_id]

    return len(expired_sessions)


@router.post("/sessions", response_model=Session)
async def create_session(request: SessionCreateRequest):
    """创建新会话"""
    session_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    session = Session(
        session_id=session_id,
        created_at=now,
        updated_at=now,
        messages=[],
        context=request.initial_context or {},
        active=True,
    )

    sessions_storage[session_id] = session
    return session


@router.get("/sessions/{session_id}", response_model=Session)
async def get_session(session_id: str):
    """获取会话详情"""
    if session_id not in sessions_storage:
        raise HTTPException(status_code=404, detail="Session not found")

    return sessions_storage[session_id]


@router.put("/sessions/{session_id}", response_model=Session)
async def update_session(session_id: str, request: SessionUpdateRequest):
    """更新会话上下文"""
    if session_id not in sessions_storage:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions_storage[session_id]
    if request.context:
        session.context.update(request.context)
    session.updated_at = datetime.utcnow().isoformat()

    return session


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    if session_id not in sessions_storage:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions_storage[session_id]
    session.active = False
    session.updated_at = datetime.utcnow().isoformat()

    return {"success": True, "message": "Session deleted successfully"}


@router.post("/sessions/{session_id}/messages", response_model=Message)
async def add_message(session_id: str, request: MessageAddRequest):
    """向会话添加消息"""
    if session_id not in sessions_storage:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions_storage[session_id]
    if not session.active:
        raise HTTPException(status_code=400, detail="Session is not active")

    message = Message(
        role=request.role,
        content=request.content,
        timestamp=datetime.utcnow().isoformat(),
        metadata=request.metadata,
    )

    session.messages.append(message)
    session.updated_at = datetime.utcnow().isoformat()

    # 限制消息历史长度（保留最近50条）
    if len(session.messages) > 50:
        session.messages = session.messages[-50:]

    return message


@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str, limit: int = 20, offset: int = 0):
    """获取会话消息历史"""
    if session_id not in sessions_storage:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions_storage[session_id]
    messages = session.messages[offset:offset + limit]

    return {
        "session_id": session_id,
        "messages": messages,
        "total": len(session.messages),
        "offset": offset,
        "limit": limit,
    }


@router.get("/sessions/{session_id}/context")
async def get_context(session_id: str):
    """获取会话上下文"""
    if session_id not in sessions_storage:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions_storage[session_id]
    return {
        "session_id": session_id,
        "context": session.context,
        "message_count": len(session.messages),
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


@router.get("/sessions")
async def list_sessions(active_only: bool = True, limit: int = 50):
    """列出所有会话"""
    cleanup_expired_sessions()

    sessions = []
    for session in sessions_storage.values():
        if active_only and not session.active:
            continue

        sessions.append({
            "session_id": session.session_id,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "message_count": len(session.messages),
            "active": session.active,
        })

    # 按更新时间倒序排序
    sessions.sort(key=lambda x: x["updated_at"], reverse=True)

    return {
        "sessions": sessions[:limit],
        "total": len(sessions),
        "active_count": sum(1 for s in sessions_storage.values() if s.active),
    }


@router.post("/sessions/cleanup")
async def cleanup_sessions():
    """手动清理过期会话"""
    cleaned = cleanup_expired_sessions()
    return {
        "success": True,
        "cleaned_sessions": cleaned,
        "remaining_sessions": len(sessions_storage),
    }


@router.get("/sessions/{session_id}/summary")
async def get_session_summary(session_id: str):
    """获取会话摘要"""
    if session_id not in sessions_storage:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions_storage[session_id]

    user_messages = [m for m in session.messages if m.role == "user"]
    assistant_messages = [m for m in session.messages if m.role == "assistant"]

    return {
        "session_id": session_id,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "active": session.active,
        "total_messages": len(session.messages),
        "user_messages": len(user_messages),
        "assistant_messages": len(assistant_messages),
        "context_keys": list(session.context.keys()),
        "duration_minutes": (
            datetime.fromisoformat(session.updated_at) -
            datetime.fromisoformat(session.created_at)
        ).total_seconds() / 60,
    }
