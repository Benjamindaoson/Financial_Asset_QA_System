"""
RAG 可观测性系统
RAG Observability System

提供完整的检索链路追踪、性能监控和质量分析
"""
import logging
import time
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class RetrievalStageMetrics:
    """单个检索阶段的指标"""
    stage_name: str
    start_time: float
    end_time: float
    duration_ms: float
    documents_retrieved: int
    top_score: float
    avg_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)


@dataclass
class RetrievalTrace:
    """完整的检索链路追踪"""
    trace_id: str
    query: str
    start_time: float
    end_time: Optional[float] = None
    total_duration_ms: Optional[float] = None
    stages: List[RetrievalStageMetrics] = field(default_factory=list)
    final_documents_count: int = 0
    final_answer_length: int = 0
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_stage(self, stage: RetrievalStageMetrics):
        """添加阶段指标"""
        self.stages.append(stage)

    def finalize(self, success: bool = True, error: Optional[str] = None):
        """完成追踪"""
        self.end_time = time.time()
        self.total_duration_ms = (self.end_time - self.start_time) * 1000
        self.success = success
        self.error = error

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "trace_id": self.trace_id,
            "query": self.query,
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "end_time": datetime.fromtimestamp(self.end_time).isoformat() if self.end_time else None,
            "total_duration_ms": self.total_duration_ms,
            "stages": [stage.to_dict() for stage in self.stages],
            "final_documents_count": self.final_documents_count,
            "final_answer_length": self.final_answer_length,
            "success": self.success,
            "error": self.error,
            "metadata": self.metadata
        }


class RAGObserver:
    """
    RAG 可观测性观察器

    功能：
    1. 链路追踪：记录每个检索阶段的耗时和结果
    2. 性能监控：统计各阶段性能指标
    3. 质量分析：分析检索质量和答案质量
    """

    def __init__(self, log_dir: Optional[str] = None):
        """
        初始化观察器

        Args:
            log_dir: 日志目录（可选）
        """
        self.traces: Dict[str, RetrievalTrace] = {}
        self.log_dir = Path(log_dir) if log_dir else None

        if self.log_dir:
            self.log_dir.mkdir(parents=True, exist_ok=True)

        # 性能统计
        self.stage_stats = defaultdict(lambda: {
            "count": 0,
            "total_duration_ms": 0.0,
            "avg_duration_ms": 0.0,
            "min_duration_ms": float('inf'),
            "max_duration_ms": 0.0
        })

    def start_trace(self, query: str, trace_id: Optional[str] = None) -> str:
        """
        开始追踪

        Args:
            query: 查询
            trace_id: 追踪ID（可选，自动生成）

        Returns:
            追踪ID
        """
        if trace_id is None:
            trace_id = self._generate_trace_id()

        trace = RetrievalTrace(
            trace_id=trace_id,
            query=query,
            start_time=time.time()
        )

        self.traces[trace_id] = trace
        logger.debug(f"开始追踪: {trace_id}, 查询: {query}")

        return trace_id

    def record_stage(
        self,
        trace_id: str,
        stage_name: str,
        documents_retrieved: int,
        top_score: float,
        avg_score: float,
        duration_ms: float,
        metadata: Optional[Dict] = None
    ):
        """
        记录阶段指标

        Args:
            trace_id: 追踪ID
            stage_name: 阶段名称
            documents_retrieved: 检索到的文档数
            top_score: 最高分数
            avg_score: 平均分数
            duration_ms: 耗时（毫秒）
            metadata: 额外元数据
        """
        if trace_id not in self.traces:
            logger.warning(f"追踪ID不存在: {trace_id}")
            return

        stage = RetrievalStageMetrics(
            stage_name=stage_name,
            start_time=time.time() - duration_ms / 1000,
            end_time=time.time(),
            duration_ms=duration_ms,
            documents_retrieved=documents_retrieved,
            top_score=top_score,
            avg_score=avg_score,
            metadata=metadata or {}
        )

        self.traces[trace_id].add_stage(stage)

        # 更新统计
        self._update_stage_stats(stage_name, duration_ms)

        logger.debug(
            f"记录阶段: {stage_name}, "
            f"耗时: {duration_ms:.2f}ms, "
            f"文档数: {documents_retrieved}, "
            f"最高分: {top_score:.3f}"
        )

    def end_trace(
        self,
        trace_id: str,
        final_documents_count: int = 0,
        final_answer_length: int = 0,
        success: bool = True,
        error: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """
        结束追踪

        Args:
            trace_id: 追踪ID
            final_documents_count: 最终文档数
            final_answer_length: 最终答案长度
            success: 是否成功
            error: 错误信息
            metadata: 额外元数据
        """
        if trace_id not in self.traces:
            logger.warning(f"追踪ID不存在: {trace_id}")
            return

        trace = self.traces[trace_id]
        trace.final_documents_count = final_documents_count
        trace.final_answer_length = final_answer_length
        trace.finalize(success=success, error=error)

        if metadata:
            trace.metadata.update(metadata)

        logger.info(
            f"追踪完成: {trace_id}, "
            f"总耗时: {trace.total_duration_ms:.2f}ms, "
            f"阶段数: {len(trace.stages)}, "
            f"成功: {success}"
        )

        # 保存到文件
        if self.log_dir:
            self._save_trace(trace)

    def get_trace(self, trace_id: str) -> Optional[RetrievalTrace]:
        """获取追踪记录"""
        return self.traces.get(trace_id)

    def get_stage_stats(self, stage_name: Optional[str] = None) -> Dict:
        """
        获取阶段统计

        Args:
            stage_name: 阶段名称（可选，返回所有阶段）

        Returns:
            统计信息
        """
        if stage_name:
            return dict(self.stage_stats.get(stage_name, {}))

        return {name: dict(stats) for name, stats in self.stage_stats.items()}

    def get_summary(self) -> Dict:
        """
        获取总体摘要

        Returns:
            摘要信息
        """
        total_traces = len(self.traces)
        successful_traces = sum(1 for t in self.traces.values() if t.success)
        failed_traces = total_traces - successful_traces

        if total_traces == 0:
            return {
                "total_traces": 0,
                "successful_traces": 0,
                "failed_traces": 0,
                "success_rate": 0.0,
                "avg_total_duration_ms": 0.0,
                "stage_stats": {}
            }

        total_duration = sum(
            t.total_duration_ms for t in self.traces.values()
            if t.total_duration_ms is not None
        )
        avg_duration = total_duration / total_traces if total_traces > 0 else 0.0

        return {
            "total_traces": total_traces,
            "successful_traces": successful_traces,
            "failed_traces": failed_traces,
            "success_rate": successful_traces / total_traces if total_traces > 0 else 0.0,
            "avg_total_duration_ms": avg_duration,
            "stage_stats": self.get_stage_stats()
        }

    def _generate_trace_id(self) -> str:
        """生成追踪ID"""
        import uuid
        return f"trace_{uuid.uuid4().hex[:12]}"

    def _update_stage_stats(self, stage_name: str, duration_ms: float):
        """更新阶段统计"""
        stats = self.stage_stats[stage_name]
        stats["count"] += 1
        stats["total_duration_ms"] += duration_ms
        stats["avg_duration_ms"] = stats["total_duration_ms"] / stats["count"]
        stats["min_duration_ms"] = min(stats["min_duration_ms"], duration_ms)
        stats["max_duration_ms"] = max(stats["max_duration_ms"], duration_ms)

    def _save_trace(self, trace: RetrievalTrace):
        """保存追踪记录到文件"""
        if not self.log_dir:
            return

        try:
            # 按日期组织文件
            date_str = datetime.now().strftime("%Y-%m-%d")
            log_file = self.log_dir / f"traces_{date_str}.jsonl"

            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(trace.to_dict(), ensure_ascii=False) + '\n')

        except Exception as e:
            logger.error(f"保存追踪记录失败: {e}")

    def export_traces(self, output_file: str):
        """
        导出所有追踪记录

        Args:
            output_file: 输出文件路径
        """
        try:
            traces_data = [trace.to_dict() for trace in self.traces.values()]

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(traces_data, f, ensure_ascii=False, indent=2)

            logger.info(f"导出 {len(traces_data)} 条追踪记录到: {output_file}")

        except Exception as e:
            logger.error(f"导出追踪记录失败: {e}")


class ObservableRAGPipeline:
    """
    可观测的 RAG 管道装饰器

    为现有的 RAG 管道添加可观测性
    """

    def __init__(self, rag_pipeline, observer: RAGObserver):
        """
        初始化

        Args:
            rag_pipeline: RAG 管道实例
            observer: 观察器
        """
        self.pipeline = rag_pipeline
        self.observer = observer

    async def search_with_observability(
        self,
        query: str,
        **kwargs
    ) -> Dict:
        """
        带可观测性的检索

        Args:
            query: 查询
            **kwargs: 其他参数

        Returns:
            检索结果（包含追踪ID）
        """
        # 开始追踪
        trace_id = self.observer.start_trace(query)

        try:
            # 1. 查询改写阶段（如果有）
            if hasattr(self.pipeline, 'query_rewriter') and kwargs.get('use_rewriter', False):
                start_time = time.time()
                rewrite_result = await self.pipeline.query_rewriter.rewrite(query)
                duration_ms = (time.time() - start_time) * 1000

                self.observer.record_stage(
                    trace_id=trace_id,
                    stage_name="query_rewriting",
                    documents_retrieved=len(rewrite_result.get('rewritten_queries', [])),
                    top_score=1.0,
                    avg_score=1.0,
                    duration_ms=duration_ms,
                    metadata={"strategy": rewrite_result.get('strategy')}
                )

            # 2. 检索阶段
            start_time = time.time()
            search_result = await self.pipeline.search(query, **kwargs)
            duration_ms = (time.time() - start_time) * 1000

            documents = search_result.documents if hasattr(search_result, 'documents') else []
            top_score = documents[0].score if documents else 0.0
            avg_score = sum(d.score for d in documents) / len(documents) if documents else 0.0

            self.observer.record_stage(
                trace_id=trace_id,
                stage_name="retrieval",
                documents_retrieved=len(documents),
                top_score=top_score,
                avg_score=avg_score,
                duration_ms=duration_ms,
                metadata={
                    "strategy": search_result.retrieval_meta.get('strategy') if hasattr(search_result, 'retrieval_meta') else 'unknown'
                }
            )

            # 3. 生成阶段（如果有）
            answer = None
            if hasattr(self.pipeline, 'generate_answer'):
                start_time = time.time()
                answer = await self.pipeline.generate_answer(query, documents)
                duration_ms = (time.time() - start_time) * 1000

                self.observer.record_stage(
                    trace_id=trace_id,
                    stage_name="generation",
                    documents_retrieved=0,
                    top_score=1.0,
                    avg_score=1.0,
                    duration_ms=duration_ms,
                    metadata={"answer_length": len(answer) if answer else 0}
                )

            # 结束追踪
            self.observer.end_trace(
                trace_id=trace_id,
                final_documents_count=len(documents),
                final_answer_length=len(answer) if answer else 0,
                success=True
            )

            # 返回结果（包含追踪ID）
            result = {
                "trace_id": trace_id,
                "query": query,
                "documents": documents,
                "answer": answer,
                "search_result": search_result
            }

            return result

        except Exception as e:
            logger.error(f"检索失败: {e}")

            # 记录失败
            self.observer.end_trace(
                trace_id=trace_id,
                success=False,
                error=str(e)
            )

            raise


# 全局观察器实例
_global_observer: Optional[RAGObserver] = None


def get_global_observer() -> RAGObserver:
    """获取全局观察器"""
    global _global_observer
    if _global_observer is None:
        _global_observer = RAGObserver(log_dir="logs/rag_traces")
    return _global_observer


def set_global_observer(observer: RAGObserver):
    """设置全局观察器"""
    global _global_observer
    _global_observer = observer


if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)

    # 创建观察器
    observer = RAGObserver(log_dir="test_logs")

    # 模拟追踪
    trace_id = observer.start_trace("什么是市盈率？")

    # 模拟各阶段
    observer.record_stage(
        trace_id=trace_id,
        stage_name="query_rewriting",
        documents_retrieved=3,
        top_score=1.0,
        avg_score=1.0,
        duration_ms=150.5
    )

    observer.record_stage(
        trace_id=trace_id,
        stage_name="retrieval",
        documents_retrieved=10,
        top_score=0.95,
        avg_score=0.75,
        duration_ms=250.3
    )

    observer.record_stage(
        trace_id=trace_id,
        stage_name="reranking",
        documents_retrieved=5,
        top_score=0.98,
        avg_score=0.85,
        duration_ms=180.7
    )

    observer.record_stage(
        trace_id=trace_id,
        stage_name="generation",
        documents_retrieved=0,
        top_score=1.0,
        avg_score=1.0,
        duration_ms=500.2
    )

    observer.end_trace(
        trace_id=trace_id,
        final_documents_count=5,
        final_answer_length=200,
        success=True
    )

    # 打印摘要
    summary = observer.get_summary()
    print("\n" + "="*60)
    print("RAG 可观测性摘要")
    print("="*60)
    print(f"总追踪数: {summary['total_traces']}")
    print(f"成功率: {summary['success_rate']:.2%}")
    print(f"平均耗时: {summary['avg_total_duration_ms']:.2f}ms")
    print("\n阶段统计:")
    for stage_name, stats in summary['stage_stats'].items():
        print(f"  {stage_name}:")
        print(f"    调用次数: {stats['count']}")
        print(f"    平均耗时: {stats['avg_duration_ms']:.2f}ms")
        print(f"    最小耗时: {stats['min_duration_ms']:.2f}ms")
        print(f"    最大耗时: {stats['max_duration_ms']:.2f}ms")
