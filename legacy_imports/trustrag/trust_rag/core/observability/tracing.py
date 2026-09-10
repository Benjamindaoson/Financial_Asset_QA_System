"""
OpenTelemetry Tracing: Production observability for TrustRAG (2026 Upgrade).

Replaces manual logging with distributed tracing, metrics, and monitoring.
Integrates with LangSmith for LLM operation tracking and cost analysis.
"""
import logging
import time
import json
from typing import Dict, Any, Optional, Callable, ContextManager
from contextlib import contextmanager
from functools import wraps

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextPropagator

from trust_rag.config import get_config

logger = logging.getLogger(__name__)


class TrustRAGTracer:
    """
    OpenTelemetry-based tracing for TrustRAG.

    Provides:
    - Distributed tracing across all components
    - Performance metrics and latency tracking
    - Error tracking and correlation
    - LangSmith integration for LLM operations
    """

    def __init__(
        self,
        service_name: str = "trust_rag",
        service_version: str = "2.0.0",
        otlp_endpoint: str = "http://localhost:4317",
        enable_langsmith: bool = True
    ):
        """
        Initialize TrustRAG tracer.

        Args:
            service_name: Service name for tracing
            service_version: Service version
            otlp_endpoint: OTLP collector endpoint
            enable_langsmith: Enable LangSmith integration
        """
        self.service_name = service_name
        self.service_version = service_version
        self.otlp_endpoint = otlp_endpoint
        self.enable_langsmith = enable_langsmith

        # Initialize OpenTelemetry
        self._setup_tracing()
        self._setup_metrics()

        # LangSmith integration
        if enable_langsmith:
            self._setup_langsmith()

        # Get tracer and meter
        self.tracer = trace.get_tracer(__name__)
        self.meter = metrics.get_meter(__name__)

        # Create metrics
        self._create_metrics()

    def _setup_tracing(self):
        """Setup OpenTelemetry tracing."""
        resource = Resource.create({
            "service.name": self.service_name,
            "service.version": self.service_version,
            "service.instance.id": "trust_rag_prod"
        })

        # Create tracer provider
        tracer_provider = TracerProvider(resource=resource)

        # Add OTLP exporter
        otlp_exporter = OTLPSpanExporter(
            endpoint=self.otlp_endpoint,
            insecure=True  # For development; use TLS in production
        )

        # Add batch processor
        span_processor = BatchSpanProcessor(otlp_exporter)
        tracer_provider.add_span_processor(span_processor)

        # Set global tracer provider
        trace.set_tracer_provider(tracer_provider)

        # Set global propagator
        trace.set_global_textmap(TraceContextPropagator())

    def _setup_metrics(self):
        """Setup OpenTelemetry metrics."""
        # Create metric exporter
        metric_exporter = OTLPMetricExporter(
            endpoint=self.otlp_endpoint,
            insecure=True
        )

        # Create metric reader
        metric_reader = PeriodicExportingMetricReader(
            exporter=metric_exporter,
            export_interval_millis=30000  # 30 seconds
        )

        # Create meter provider
        meter_provider = MeterProvider(
            metric_readers=[metric_reader],
            resource=Resource.create({
                "service.name": f"{self.service_name}_metrics"
            })
        )

        # Set global meter provider
        metrics.set_meter_provider(meter_provider)

    def _setup_langsmith(self):
        """Setup LangSmith integration for LLM operations."""
        try:
            import langsmith
            from langsmith import traceable

            # Configure LangSmith (would use env vars in production)
            langsmith_client = langsmith.Client()

            # Store LangSmith client for LLM operations
            self.langsmith_client = langsmith_client
            self.traceable = traceable

            logger.info("LangSmith integration enabled")

        except ImportError:
            logger.warning("LangSmith not installed. Install with: pip install langsmith")
            self.enable_langsmith = False

    def _create_metrics(self):
        """Create application metrics."""
        # Query metrics
        self.query_counter = self.meter.create_counter(
            "trust_rag_queries_total",
            description="Total number of queries processed",
            unit="1"
        )

        self.query_duration = self.meter.create_histogram(
            "trust_rag_query_duration_seconds",
            description="Query processing duration",
            unit="s"
        )

        # Retrieval metrics
        self.retrieval_counter = self.meter.create_counter(
            "trust_rag_retrieval_total",
            description="Total retrieval operations",
            unit="1"
        )

        self.retrieval_candidates = self.meter.create_histogram(
            "trust_rag_retrieval_candidates",
            description="Number of candidates retrieved",
            unit="1"
        )

        # Generation metrics
        self.generation_counter = self.meter.create_counter(
            "trust_rag_generation_total",
            description="Total generation operations",
            unit="1"
        )

        self.token_usage = self.meter.create_counter(
            "trust_rag_tokens_total",
            description="Total tokens used",
            unit="1"
        )

        # Error metrics
        self.error_counter = self.meter.create_counter(
            "trust_rag_errors_total",
            description="Total errors by type",
            unit="1"
        )

    @contextmanager
    def trace_query(self, query: str, query_type: str = "unknown"):
        """
        Context manager for tracing complete query execution.

        Args:
            query: Query string
            query_type: Type of query (factual, summary, etc.)
        """
        with self.tracer.start_as_current_span(
            "query_processing",
            kind=trace.SpanKind.INTERNAL
        ) as span:
            # Add query metadata
            span.set_attribute("query.text", query[:500])  # Truncate long queries
            span.set_attribute("query.type", query_type)
            span.set_attribute("query.length", len(query))

            start_time = time.time()
            try:
                yield span
                span.set_status(Status(StatusCode.OK))

                # Record metrics
                duration = time.time() - start_time
                self.query_duration.record(duration, {
                    "query_type": query_type
                })
                self.query_counter.add(1, {
                    "query_type": query_type,
                    "status": "success"
                })

            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)

                # Record error metrics
                self.error_counter.add(1, {
                    "error_type": "query_processing",
                    "query_type": query_type
                })
                raise

    @contextmanager
    def trace_retrieval(
        self,
        query: str,
        strategy: str,
        expected_candidates: int = 0
    ):
        """
        Context manager for tracing retrieval operations.

        Args:
            query: Query string
            strategy: Retrieval strategy used
            expected_candidates: Expected number of candidates
        """
        with self.tracer.start_as_current_span(
            "retrieval_operation",
            kind=trace.SpanKind.INTERNAL
        ) as span:
            span.set_attribute("retrieval.query", query[:200])
            span.set_attribute("retrieval.strategy", strategy)
            span.set_attribute("retrieval.expected_candidates", expected_candidates)

            start_time = time.time()
            candidates_returned = 0

            try:
                yield span

                span.set_attribute("retrieval.candidates_returned", candidates_returned)
                span.set_status(Status(StatusCode.OK))

                # Record metrics
                duration = time.time() - start_time
                self.retrieval_counter.add(1, {
                    "strategy": strategy,
                    "status": "success"
                })
                self.retrieval_candidates.record(candidates_returned, {
                    "strategy": strategy
                })

            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))

                self.error_counter.add(1, {
                    "error_type": "retrieval",
                    "strategy": strategy
                })
                raise

    @contextmanager
    def trace_generation(
        self,
        prompt: str,
        model: str,
        max_tokens: int = 0
    ):
        """
        Context manager for tracing LLM generation operations.

        Args:
            prompt: Input prompt
            model: Model name
            max_tokens: Maximum tokens to generate
        """
        with self.tracer.start_as_current_span(
            "llm_generation",
            kind=trace.SpanKind.INTERNAL
        ) as span:
            span.set_attribute("llm.model", model)
            span.set_attribute("llm.prompt_length", len(prompt))
            span.set_attribute("llm.max_tokens", max_tokens)

            # LangSmith integration
            if self.enable_langsmith:
                span.set_attribute("langsmith.run_name", f"generation_{model}")

            start_time = time.time()
            tokens_used = 0

            try:
                yield span

                span.set_attribute("llm.tokens_used", tokens_used)
                span.set_status(Status(StatusCode.OK))

                # Record metrics
                duration = time.time() - start_time
                self.generation_counter.add(1, {
                    "model": model,
                    "status": "success"
                })
                self.token_usage.add(tokens_used, {
                    "model": model,
                    "operation": "generation"
                })

            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))

                self.error_counter.add(1, {
                    "error_type": "generation",
                    "model": model
                })
                raise

    def trace_method(
        self,
        operation_name: str,
        attributes: Optional[Dict[str, Any]] = None
    ):
        """
        Decorator for tracing method execution.

        Args:
            operation_name: Name of the operation
            attributes: Additional span attributes
        """
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                with self.tracer.start_as_current_span(
                    operation_name,
                    kind=trace.SpanKind.INTERNAL
                ) as span:
                    # Set attributes
                    if attributes:
                        for key, value in attributes.items():
                            span.set_attribute(key, value)

                    # Add function metadata
                    span.set_attribute("function.name", func.__name__)
                    span.set_attribute("function.module", func.__module__)

                    try:
                        result = func(*args, **kwargs)
                        span.set_status(Status(StatusCode.OK))
                        return result

                    except Exception as e:
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        raise

            return wrapper
        return decorator

    def create_child_span(
        self,
        name: str,
        parent_span=None,
        attributes: Optional[Dict[str, Any]] = None
    ) -> ContextManager:
        """
        Create a child span for nested operations.

        Args:
            name: Span name
            parent_span: Parent span (uses current if None)
            attributes: Span attributes

        Returns:
            Context manager for the span
        """
        @contextmanager
        def span_context():
            with self.tracer.start_as_current_span(
                name,
                kind=trace.SpanKind.INTERNAL
            ) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)

                try:
                    yield span
                    span.set_status(Status(StatusCode.OK))
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise

        return span_context()

    def get_trace_context(self) -> Dict[str, str]:
        """
        Get current trace context for propagation.

        Returns:
            Trace context headers
        """
        carrier = {}
        TraceContextPropagator().inject(carrier)
        return carrier

    def set_trace_context(self, headers: Dict[str, str]):
        """
        Set trace context from headers.

        Args:
            headers: Trace context headers
        """
        TraceContextPropagator().extract(headers)

    def flush(self):
        """Flush all pending telemetry data."""
        # Force flush spans
        trace.get_tracer_provider().force_flush(timeout_millis=5000)

        # Force flush metrics
        metrics.get_meter_provider().force_flush(timeout_millis=5000)


# Global tracer instance
_tracer_instance = None

def get_tracer() -> TrustRAGTracer:
    """Get global tracer instance."""
    global _tracer_instance
    if _tracer_instance is None:
        _tracer_instance = TrustRAGTracer()
    return _tracer_instance


# Convenience functions for easy tracing
def trace_query(query: str, query_type: str = "unknown"):
    """Convenience function for query tracing."""
    return get_tracer().trace_query(query, query_type)

def trace_retrieval(query: str, strategy: str, expected_candidates: int = 0):
    """Convenience function for retrieval tracing."""
    return get_tracer().trace_retrieval(query, strategy, expected_candidates)

def trace_generation(prompt: str, model: str, max_tokens: int = 0):
    """Convenience function for generation tracing."""
    return get_tracer().trace_generation(prompt, model, max_tokens)
