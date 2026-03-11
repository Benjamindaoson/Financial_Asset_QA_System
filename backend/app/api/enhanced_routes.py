"""
增强版API路由 - 暴露所有高级功能
Enhanced API Routes - Expose All Advanced Features
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional
import json

from app.models import ChatRequest
from app.agent.enhanced_core import EnhancedAgentCore

router = APIRouter(prefix="/api/v1/enhanced", tags=["enhanced"])


@router.post("/chat")
async def chat_enhanced(
    request: ChatRequest,
    enable_validation: bool = True,
    enable_intent_recognition: bool = True,
):
    """
    增强版聊天接口

    Args:
        request: 聊天请求
        enable_validation: 是否启用多数据源验证
        enable_intent_recognition: 是否启用意图识别

    Returns:
        流式响应
    """
    try:
        agent = EnhancedAgentCore()

        async def event_generator():
            async for event in agent.run_enhanced(
                query=request.query,
                model_name=request.model_name,
                enable_validation=enable_validation,
                enable_intent_recognition=enable_intent_recognition,
            ):
                # 转换为SSE格式
                event_data = {
                    "type": event.type,
                    "text": event.text,
                    "data": event.data,
                }
                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"

            yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/price")
async def get_price_validated(
    symbol: str,
    validate: bool = True,
):
    """
    获取价格（带多数据源验证）

    Args:
        symbol: 股票代码
        validate: 是否启用验证

    Returns:
        价格信息和验证结果
    """
    try:
        agent = EnhancedAgentCore()
        result = await agent.enhanced_market_service.get_price_with_validation(
            symbol, validate=validate
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/change")
async def get_change_analysis(
    symbol: str,
    days: int = 7,
):
    """
    获取深度涨跌分析

    Args:
        symbol: 股票代码
        days: 天数

    Returns:
        涨跌分析结果
    """
    try:
        agent = EnhancedAgentCore()
        result = await agent.enhanced_market_service.get_enhanced_change_analysis(
            symbol, days=days
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/knowledge")
async def search_with_intent(
    query: str,
):
    """
    知识检索（带意图识别）

    Args:
        query: 查询文本

    Returns:
        自适应回答
    """
    try:
        agent = EnhancedAgentCore()
        result = await agent.enhanced_rag_pipeline.search_with_intent(query)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/route")
async def classify_query(
    query: str,
):
    """
    查询分类（带置信度评估）

    Args:
        query: 查询文本

    Returns:
        路由决策和置信度
    """
    try:
        agent = EnhancedAgentCore()
        result = await agent.enhanced_router.classify_with_confidence(query)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/format")
async def format_answer(
    query: str,
    data: dict,
):
    """
    智能格式化

    Args:
        query: 查询文本
        data: 数据

    Returns:
        格式化后的结构化数据
    """
    try:
        agent = EnhancedAgentCore()
        result = agent.smart_formatter.format_answer(query, data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
