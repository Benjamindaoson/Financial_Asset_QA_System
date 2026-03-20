"""Prometheus metrics for monitoring."""

from prometheus_client import Counter, Histogram, Gauge, Info
import logging

logger = logging.getLogger(__name__)

# Try to import prometheus_client, but don't fail if not available
try:
    from prometheus_client import Counter, Histogram, Gauge, Info
    PROMETHEUS_AVAILABLE = True
except ImportError:
    logger.warning("prometheus_client not installed, metrics disabled")
    PROMETHEUS_AVAILABLE = False
    # Create dummy classes that do nothing
    class Counter:
        def __init__(self, *args, **kwargs):
            pass
        def labels(self, *args, **kwargs):
            return self
        def inc(self, *args, **kwargs):
            pass

    class Histogram:
        def __init__(self, *args, **kwargs):
            pass
        def labels(self, *args, **kwargs):
            return self
        def observe(self, *args, **kwargs):
            pass

    class Gauge:
        def __init__(self, *args, **kwargs):
            pass
        def set(self, *args, **kwargs):
            pass
        def inc(self, *args, **kwargs):
            pass
        def dec(self, *args, **kwargs):
            pass

    class Info:
        def __init__(self, *args, **kwargs):
            pass
        def info(self, *args, **kwargs):
            pass


# Business metrics
query_total = Counter(
    'financial_qa_query_total',
    'Total number of queries',
    ['query_type', 'status']
)

query_duration = Histogram(
    'financial_qa_query_duration_seconds',
    'Query processing duration',
    ['query_type']
)

tool_execution_duration = Histogram(
    'financial_qa_tool_duration_seconds',
    'Tool execution duration',
    ['tool_name', 'status']
)

tool_execution_total = Counter(
    'financial_qa_tool_execution_total',
    'Total tool executions',
    ['tool_name', 'status']
)

confidence_score = Histogram(
    'financial_qa_confidence_score',
    'Response confidence score',
    ['query_type'],
    buckets=[0.0, 0.3, 0.5, 0.7, 0.85, 0.95, 1.0]
)

response_guard_blocks = Counter(
    'financial_qa_response_guard_blocks_total',
    'Number of responses blocked by ResponseGuard'
)

data_validator_blocks = Counter(
    'financial_qa_data_validator_blocks_total',
    'Number of responses blocked by DataValidator'
)

# Infrastructure metrics
redis_operations = Counter(
    'financial_qa_redis_operations_total',
    'Redis operations',
    ['operation', 'status']
)

redis_hit_rate = Gauge(
    'financial_qa_redis_hit_rate',
    'Cache hit rate'
)

chromadb_query_duration = Histogram(
    'financial_qa_chromadb_query_duration_seconds',
    'ChromaDB query duration'
)

rag_retrieval_total = Counter(
    'financial_qa_rag_retrieval_total',
    'RAG retrieval operations',
    ['method', 'status']
)

# LLM metrics
llm_token_usage = Counter(
    'financial_qa_llm_tokens_total',
    'LLM token usage',
    ['model', 'type']  # type: input/output
)

llm_request_duration = Histogram(
    'financial_qa_llm_request_duration_seconds',
    'LLM request duration',
    ['model', 'status']
)

llm_request_total = Counter(
    'financial_qa_llm_request_total',
    'Total LLM requests',
    ['model', 'status']
)

# System info
system_info = Info(
    'financial_qa_system',
    'System information'
)


class MetricsCollector:
    """Helper class for collecting metrics."""

    @staticmethod
    def record_query(query_type: str, status: str, duration: float):
        """Record query metrics."""
        query_total.labels(query_type=query_type, status=status).inc()
        query_duration.labels(query_type=query_type).observe(duration)

    @staticmethod
    def record_tool_execution(tool_name: str, status: str, duration: float):
        """Record tool execution metrics."""
        tool_execution_total.labels(tool_name=tool_name, status=status).inc()
        tool_execution_duration.labels(tool_name=tool_name, status=status).observe(duration)

    @staticmethod
    def record_confidence(query_type: str, score: float):
        """Record confidence score."""
        confidence_score.labels(query_type=query_type).observe(score)

    @staticmethod
    def record_guard_block():
        """Record ResponseGuard block."""
        response_guard_blocks.inc()

    @staticmethod
    def record_validator_block():
        """Record DataValidator block."""
        data_validator_blocks.inc()

    @staticmethod
    def record_redis_operation(operation: str, status: str):
        """Record Redis operation."""
        redis_operations.labels(operation=operation, status=status).inc()

    @staticmethod
    def update_redis_hit_rate(hit_rate: float):
        """Update Redis hit rate."""
        redis_hit_rate.set(hit_rate)

    @staticmethod
    def record_chromadb_query(duration: float):
        """Record ChromaDB query."""
        chromadb_query_duration.observe(duration)

    @staticmethod
    def record_rag_retrieval(method: str, status: str):
        """Record RAG retrieval."""
        rag_retrieval_total.labels(method=method, status=status).inc()

    @staticmethod
    def record_llm_tokens(model: str, input_tokens: int, output_tokens: int):
        """Record LLM token usage."""
        llm_token_usage.labels(model=model, type='input').inc(input_tokens)
        llm_token_usage.labels(model=model, type='output').inc(output_tokens)

    @staticmethod
    def record_llm_request(model: str, status: str, duration: float):
        """Record LLM request."""
        llm_request_total.labels(model=model, status=status).inc()
        llm_request_duration.labels(model=model, status=status).observe(duration)

    @staticmethod
    def set_system_info(version: str, environment: str):
        """Set system information."""
        system_info.info({
            'version': version,
            'environment': environment
        })
