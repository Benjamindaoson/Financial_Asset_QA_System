"""
Service Mesh for GraphRAG Microservices.

This module provides service mesh functionality for advanced service-to-service
communication, including circuit breaking, load balancing, and observability.
"""

import logging
from typing import Dict, List, Any, Optional, Callable, Union
import time
import asyncio
import aiohttp
from aiohttp import web
import threading
from collections import defaultdict
import json
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class ServiceEndpoint:
    """Service endpoint information."""
    service_name: str
    url: str
    weight: int = 1
    healthy: bool = True
    last_failure: float = 0
    failure_count: int = 0


@dataclass
class CircuitBreaker:
    """Circuit breaker for service calls."""
    service_name: str
    state: CircuitState = CircuitState.CLOSED
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    success_threshold: int = 3
    last_failure_time: float = 0
    consecutive_successes: int = 0
    consecutive_failures: int = 0

    def record_success(self):
        """Record a successful call."""
        self.consecutive_successes += 1
        self.consecutive_failures = 0

        if self.state == CircuitState.HALF_OPEN and self.consecutive_successes >= self.success_threshold:
            self.state = CircuitState.CLOSED
            self.consecutive_successes = 0
            logger.info(f"Circuit breaker for {self.service_name} closed")

    def record_failure(self):
        """Record a failed call."""
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.last_failure_time = time.time()

        if self.state == CircuitState.CLOSED and self.consecutive_failures >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker for {self.service_name} opened")
        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker for {self.service_name} re-opened")

    def can_attempt_call(self) -> bool:
        """Check if a call can be attempted."""
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker for {self.service_name} half-open")
                return True
            return False
        else:  # HALF_OPEN
            return True


class ServiceMesh:
    """
    Service mesh for advanced microservice communication and observability.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize service mesh.

        Args:
            config: Mesh configuration
        """
        self.config = config or {}

        # Service registry integration
        self.service_registry = None

        # Circuit breakers
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}

        # Service endpoints cache
        self.endpoints_cache: Dict[str, List[ServiceEndpoint]] = {}
        self.cache_ttl = self.config.get('cache_ttl', 30.0)  # seconds
        self.cache_timestamps: Dict[str, float] = {}

        # Load balancing strategies
        self.load_balancers = {
            'round_robin': self._round_robin_select,
            'weighted_round_robin': self._weighted_round_robin_select,
            'least_connections': self._least_connections_select,
            'random': self._random_select
        }
        self.default_lb_strategy = self.config.get('load_balancing', 'round_robin')

        # Request tracking
        self.request_counters: Dict[str, int] = defaultdict(int)
        self.active_requests: Dict[str, int] = defaultdict(int)
        self.round_robin_index: Dict[str, int] = defaultdict(int)

        # Observability
        self.request_metrics = defaultdict(list)
        self.max_metrics_history = 1000

        # HTTP client
        self.http_session = None
        self._init_http_client()

        # Mesh settings
        self.request_timeout = self.config.get('request_timeout', 30.0)
        self.retry_attempts = self.config.get('retry_attempts', 3)
        self.retry_delay = self.config.get('retry_delay', 1.0)

        logger.info("Service mesh initialized")

    def set_service_registry(self, registry):
        """Set service registry for service discovery."""
        self.service_registry = registry
        logger.info("Service registry connected to service mesh")

    def _init_http_client(self):
        """Initialize HTTP client with connection pooling."""
        connector = aiohttp.TCPConnector(
            limit=self.config.get('max_connections', 100),
            limit_per_host=self.config.get('max_connections_per_host', 10),
            ttl_dns_cache=self.config.get('dns_cache_ttl', 300)
        )

        timeout = aiohttp.ClientTimeout(total=self.request_timeout)
        self.http_session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={'User-Agent': 'GraphRAG-ServiceMesh/1.0'}
        )

    async def call_service(
        self,
        service_name: str,
        endpoint: str,
        method: str = 'GET',
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        lb_strategy: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Call a service through the service mesh.

        Args:
            service_name: Target service name
            endpoint: Service endpoint path
            method: HTTP method
            data: Request data
            headers: Request headers
            lb_strategy: Load balancing strategy

        Returns:
            Response from service call
        """
        start_time = time.time()
        call_id = f"{service_name}_{int(start_time * 1000)}"

        try:
            # Get service endpoints
            endpoints = await self._get_service_endpoints(service_name)
            if not endpoints:
                raise ValueError(f"No endpoints available for service: {service_name}")

            # Select endpoint using load balancing
            strategy = lb_strategy or self.default_lb_strategy
            selected_endpoint = self._select_endpoint(service_name, endpoints, strategy)

            if not selected_endpoint:
                raise ValueError(f"No healthy endpoint available for service: {service_name}")

            # Check circuit breaker
            circuit_breaker = self.circuit_breakers.get(service_name)
            if circuit_breaker and not circuit_breaker.can_attempt_call():
                raise Exception(f"Circuit breaker open for service: {service_name}")

            # Increment active requests
            self.active_requests[service_name] += 1

            # Make the call
            result = await self._make_http_call(
                selected_endpoint.url + endpoint,
                method,
                data,
                headers
            )

            # Record success
            if circuit_breaker:
                circuit_breaker.record_success()

            # Record metrics
            response_time = time.time() - start_time
            self._record_request_metrics(service_name, response_time, True, result.get('status_code'))

            result.update({
                'call_id': call_id,
                'service_name': service_name,
                'endpoint': selected_endpoint.url + endpoint,
                'response_time': response_time,
                'lb_strategy': strategy
            })

            return result

        except Exception as e:
            # Record failure
            response_time = time.time() - start_time
            circuit_breaker = self.circuit_breakers.get(service_name)
            if circuit_breaker:
                circuit_breaker.record_failure()

            self._record_request_metrics(service_name, response_time, False, None)

            logger.error(f"Service call failed: {service_name} - {e}")
            return {
                'call_id': call_id,
                'service_name': service_name,
                'success': False,
                'error': str(e),
                'response_time': response_time
            }

        finally:
            # Decrement active requests
            if self.active_requests[service_name] > 0:
                self.active_requests[service_name] -= 1

    async def _get_service_endpoints(self, service_name: str) -> List[ServiceEndpoint]:
        """Get healthy endpoints for a service."""
        # Check cache first
        current_time = time.time()
        if (service_name in self.endpoints_cache and
            current_time - self.cache_timestamps.get(service_name, 0) < self.cache_ttl):
            return self.endpoints_cache[service_name]

        # Fetch from service registry
        if not self.service_registry:
            return []

        try:
            instances = self.service_registry.discover_service(service_name)
            endpoints = []

            for instance in instances:
                if instance.is_healthy():
                    endpoint = ServiceEndpoint(
                        service_name=service_name,
                        url=instance.get_url(),
                        weight=1,  # Could be based on instance metadata
                        healthy=True
                    )
                    endpoints.append(endpoint)

            # Cache endpoints
            self.endpoints_cache[service_name] = endpoints
            self.cache_timestamps[service_name] = current_time

            return endpoints

        except Exception as e:
            logger.error(f"Failed to get service endpoints: {e}")
            return []

    def _select_endpoint(self, service_name: str, endpoints: List[ServiceEndpoint],
                        strategy: str) -> Optional[ServiceEndpoint]:
        """Select an endpoint using the specified load balancing strategy."""
        if not endpoints:
            return None

        # Filter healthy endpoints
        healthy_endpoints = [ep for ep in endpoints if ep.healthy]

        if not healthy_endpoints:
            return None

        # Use the specified strategy
        selector = self.load_balancers.get(strategy, self._round_robin_select)
        return selector(service_name, healthy_endpoints)

    def _round_robin_select(self, service_name: str, endpoints: List[ServiceEndpoint]) -> ServiceEndpoint:
        """Round-robin endpoint selection."""
        current_index = self.round_robin_index[service_name]
        selected = endpoints[current_index % len(endpoints)]
        self.round_robin_index[service_name] = (current_index + 1) % len(endpoints)
        return selected

    def _weighted_round_robin_select(self, service_name: str, endpoints: List[ServiceEndpoint]) -> ServiceEndpoint:
        """Weighted round-robin endpoint selection."""
        total_weight = sum(ep.weight for ep in endpoints)
        if total_weight == 0:
            return self._round_robin_select(service_name, endpoints)

        # Simple weighted selection (could be optimized)
        current_index = self.round_robin_index[service_name]
        cumulative_weight = 0

        for endpoint in endpoints:
            cumulative_weight += endpoint.weight
            if current_index < cumulative_weight:
                self.round_robin_index[service_name] = (current_index + 1) % total_weight
                return endpoint

        # Fallback
        return endpoints[0]

    def _least_connections_select(self, service_name: str, endpoints: List[ServiceEndpoint]) -> ServiceEndpoint:
        """Least connections endpoint selection."""
        # This is a simplified version - in practice, you'd track actual connections
        # For now, use round-robin as approximation
        return self._round_robin_select(service_name, endpoints)

    def _random_select(self, service_name: str, endpoints: List[ServiceEndpoint]) -> ServiceEndpoint:
        """Random endpoint selection."""
        import random
        return random.choice(endpoints)

    async def _make_http_call(self, url: str, method: str, data: Any = None,
                            headers: Dict[str, str] = None) -> Dict[str, Any]:
        """Make HTTP call with retry logic."""
        headers = headers or {}
        headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

        last_error = None

        for attempt in range(self.retry_attempts):
            try:
                # Prepare request data
                json_data = None
                if data is not None:
                    if isinstance(data, (dict, list)):
                        json_data = data
                    else:
                        json_data = {'data': str(data)}

                # Make request
                async with self.http_session.request(
                    method=method,
                    url=url,
                    json=json_data,
                    headers=headers
                ) as response:

                    # Parse response
                    response_data = {}
                    if response.headers.get('content-type', '').startswith('application/json'):
                        response_data = await response.json()
                    else:
                        response_data = {'text': await response.text()}

                    return {
                        'success': response.status == 200,
                        'status_code': response.status,
                        'headers': dict(response.headers),
                        'data': response_data
                    }

            except asyncio.TimeoutError:
                last_error = "Request timeout"
            except aiohttp.ClientError as e:
                last_error = f"HTTP client error: {e}"
            except Exception as e:
                last_error = f"Unexpected error: {e}"

            # Wait before retry
            if attempt < self.retry_attempts - 1:
                await asyncio.sleep(self.retry_delay * (attempt + 1))

        # All retries failed
        raise Exception(f"HTTP call failed after {self.retry_attempts} attempts: {last_error}")

    def _record_request_metrics(self, service_name: str, response_time: float,
                               success: bool, status_code: Optional[int]):
        """Record request metrics for observability."""
        metric = {
            'timestamp': time.time(),
            'service_name': service_name,
            'response_time': response_time,
            'success': success,
            'status_code': status_code
        }

        self.request_metrics[service_name].append(metric)

        # Maintain history size
        if len(self.request_metrics[service_name]) > self.max_metrics_history:
            self.request_metrics[service_name] = self.request_metrics[service_name][-self.max_metrics_history:]

    def get_circuit_breaker_status(self, service_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get circuit breaker status.

        Args:
            service_name: Specific service, or None for all

        Returns:
            Circuit breaker status
        """
        if service_name:
            breaker = self.circuit_breakers.get(service_name)
            if not breaker:
                return {'status': 'not_found', 'service_name': service_name}

            return {
                'service_name': service_name,
                'state': breaker.state.value,
                'consecutive_failures': breaker.consecutive_failures,
                'consecutive_successes': breaker.consecutive_successes,
                'last_failure_time': breaker.last_failure_time
            }

        # All circuit breakers
        return {
            service_name: {
                'state': breaker.state.value,
                'consecutive_failures': breaker.consecutive_failures,
                'last_failure_time': breaker.last_failure_time
            }
            for service_name, breaker in self.circuit_breakers.items()
        }

    def configure_circuit_breaker(self, service_name: str, failure_threshold: int = 5,
                                 recovery_timeout: float = 60.0, success_threshold: int = 3):
        """
        Configure circuit breaker for a service.

        Args:
            service_name: Service name
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time to wait before attempting recovery
            success_threshold: Number of successes needed to close circuit
        """
        self.circuit_breakers[service_name] = CircuitBreaker(
            service_name=service_name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            success_threshold=success_threshold
        )
        logger.info(f"Configured circuit breaker for {service_name}")

    def get_mesh_metrics(self) -> Dict[str, Any]:
        """Get service mesh metrics."""
        total_requests = sum(len(metrics) for metrics in self.request_metrics.values())

        # Calculate success rate and avg response time
        all_metrics = []
        for service_metrics in self.request_metrics.values():
            all_metrics.extend(service_metrics)

        if all_metrics:
            success_rate = sum(1 for m in all_metrics if m['success']) / len(all_metrics)
            avg_response_time = sum(m['response_time'] for m in all_metrics) / len(all_metrics)
        else:
            success_rate = 0.0
            avg_response_time = 0.0

        return {
            'total_requests': total_requests,
            'success_rate': success_rate,
            'avg_response_time': avg_response_time,
            'active_circuit_breakers': len(self.circuit_breakers),
            'services_with_metrics': len(self.request_metrics),
            'active_requests': dict(self.active_requests)
        }

    def get_service_metrics(self, service_name: str, time_window: float = 3600.0) -> Dict[str, Any]:
        """
        Get metrics for a specific service.

        Args:
            service_name: Service name
            time_window: Time window in seconds

        Returns:
            Service metrics
        """
        current_time = time.time()
        window_start = current_time - time_window

        metrics = self.request_metrics.get(service_name, [])
        recent_metrics = [m for m in metrics if m['timestamp'] > window_start]

        if not recent_metrics:
            return {'status': 'no_data', 'service_name': service_name}

        success_count = sum(1 for m in recent_metrics if m['success'])
        total_count = len(recent_metrics)

        return {
            'service_name': service_name,
            'time_window': time_window,
            'total_requests': total_count,
            'successful_requests': success_count,
            'success_rate': success_count / total_count if total_count > 0 else 0,
            'avg_response_time': sum(m['response_time'] for m in recent_metrics) / total_count,
            'error_rate': (total_count - success_count) / total_count if total_count > 0 else 0
        }

    def enable_service_observability(self, service_name: str):
        """
        Enable detailed observability for a service.

        Args:
            service_name: Service name
        """
        # Configure circuit breaker if not already configured
        if service_name not in self.circuit_breakers:
            self.configure_circuit_breaker(service_name)

        logger.info(f"Observability enabled for service: {service_name}")

    def set_load_balancing_strategy(self, service_name: str, strategy: str):
        """
        Set load balancing strategy for a service.

        Args:
            service_name: Service name
            strategy: Load balancing strategy
        """
        if strategy not in self.load_balancers:
            raise ValueError(f"Unknown load balancing strategy: {strategy}")

        # Store per-service strategy (not implemented in this simplified version)
        logger.info(f"Load balancing strategy for {service_name} set to: {strategy}")

    async def close(self):
        """Close the service mesh and cleanup resources."""
        if self.http_session:
            await self.http_session.close()
            logger.info("Service mesh HTTP session closed")

    def __del__(self):
        """Destructor to ensure cleanup."""
        if hasattr(self, 'http_session') and self.http_session:
            # Note: This is not ideal for async cleanup, but better than nothing
            logger.warning("Service mesh not properly closed - HTTP session may leak")
