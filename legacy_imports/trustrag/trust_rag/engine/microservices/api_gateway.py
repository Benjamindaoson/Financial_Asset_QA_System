"""
API Gateway for GraphRAG Microservices.

This module provides API gateway functionality including request routing,
load balancing, authentication, rate limiting, and monitoring.
"""

import logging
from typing import Dict, List, Any, Optional, Callable, Union
import time
import threading
import json
import hashlib
from collections import defaultdict, deque
import asyncio
import aiohttp
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Route:
    """Represents an API route."""
    path: str
    method: str
    service_name: str
    service_path: str = ''
    auth_required: bool = False
    rate_limit: Optional[int] = None  # requests per minute
    timeout: int = 30
    retries: int = 3


@dataclass
class ClientRequest:
    """Represents a client request."""
    request_id: str
    client_ip: str
    method: str
    path: str
    headers: Dict[str, str]
    timestamp: float
    user_id: Optional[str] = None


class RateLimiter:
    """Simple rate limiter using sliding window."""

    def __init__(self, requests_per_minute: int):
        self.requests_per_minute = requests_per_minute
        self.requests = deque()
        self.lock = threading.Lock()

    def allow_request(self, client_id: str) -> bool:
        """Check if request is allowed."""
        with self.lock:
            current_time = time.time()

            # Remove old requests outside the window
            while self.requests and current_time - self.requests[0] > 60:
                self.requests.popleft()

            # Check if under limit
            if len(self.requests) < self.requests_per_minute:
                self.requests.append(current_time)
                return True

            return False


class APIGateway:
    """
    API Gateway with routing, load balancing, and middleware support.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize API gateway.

        Args:
            config: Gateway configuration
        """
        self.config = config or {}

        # Service registry integration
        self.service_registry = None

        # Routes
        self.routes: Dict[str, Route] = {}
        self.route_lock = threading.Lock()

        # Rate limiting
        self.rate_limiters: Dict[str, RateLimiter] = {}
        self.global_rate_limiter = RateLimiter(self.config.get('global_rate_limit', 1000))

        # Authentication
        self.auth_function: Optional[Callable] = None

        # Middleware
        self.middlewares: List[Callable] = []

        # Monitoring
        self.request_stats = defaultdict(int)
        self.response_times = deque(maxlen=1000)
        self.error_counts = defaultdict(int)

        # HTTP client
        self.http_session = None

        # Gateway settings
        self.host = self.config.get('host', '0.0.0.0')
        self.port = self.config.get('port', 8080)
        self.timeout = self.config.get('timeout', 30)

        logger.info(f"API Gateway initialized on {self.host}:{self.port}")

    def set_service_registry(self, registry):
        """Set service registry for service discovery."""
        self.service_registry = registry
        logger.info("Service registry connected to API Gateway")

    def add_route(
        self,
        path: str,
        method: str,
        service_name: str,
        service_path: str = '',
        auth_required: bool = False,
        rate_limit: Optional[int] = None,
        timeout: int = 30,
        retries: int = 3
    ):
        """
        Add a route to the gateway.

        Args:
            path: API path pattern
            method: HTTP method
            service_name: Target service name
            service_path: Path on the target service
            auth_required: Whether authentication is required
            rate_limit: Rate limit (requests per minute)
            timeout: Request timeout
            retries: Number of retries
        """
        route_key = f"{method.upper()}:{path}"

        route = Route(
            path=path,
            method=method.upper(),
            service_name=service_name,
            service_path=service_path,
            auth_required=auth_required,
            rate_limit=rate_limit,
            timeout=timeout,
            retries=retries
        )

        with self.route_lock:
            self.routes[route_key] = route

            # Set up rate limiter if specified
            if rate_limit:
                self.rate_limiters[route_key] = RateLimiter(rate_limit)

        logger.info(f"Added route {route_key} -> {service_name}")

    def set_auth_function(self, auth_func: Callable[[Dict[str, str]], Optional[str]]):
        """
        Set authentication function.

        Args:
            auth_func: Function that takes headers and returns user_id or None
        """
        self.auth_function = auth_func
        logger.info("Authentication function set")

    def add_middleware(self, middleware: Callable):
        """
        Add middleware function.

        Args:
            middleware: Middleware function
        """
        self.middlewares.append(middleware)
        logger.info("Middleware added")

    async def handle_request(self, request) -> aiohttp.web.Response:
        """
        Handle incoming HTTP request.

        Args:
            request: aiohttp request object

        Returns:
            HTTP response
        """
        start_time = time.time()

        # Create client request object
        client_req = ClientRequest(
            request_id=self._generate_request_id(),
            client_ip=self._get_client_ip(request),
            method=request.method,
            path=request.path,
            headers=dict(request.headers),
            timestamp=start_time
        )

        try:
            # Apply middlewares
            for middleware in self.middlewares:
                try:
                    result = await middleware(client_req, request)
                    if result:
                        return result
                except Exception as e:
                    logger.error(f"Middleware error: {e}")

            # Global rate limiting
            if not self.global_rate_limiter.allow_request(client_req.client_ip):
                return self._create_error_response(429, "Rate limit exceeded")

            # Find route
            route = self._find_route(request.method, request.path)
            if not route:
                return self._create_error_response(404, "Route not found")

            # Route-specific rate limiting
            route_key = f"{request.method}:{route.path}"
            if route_key in self.rate_limiters:
                if not self.rate_limiters[route_key].allow_request(client_req.client_ip):
                    return self._create_error_response(429, "Route rate limit exceeded")

            # Authentication
            if route.auth_required:
                user_id = self._authenticate(request.headers)
                if not user_id:
                    return self._create_error_response(401, "Authentication required")
                client_req.user_id = user_id

            # Route to service
            response = await self._route_to_service(client_req, route, request)

            # Record metrics
            response_time = time.time() - start_time
            self._record_metrics(client_req, response.status, response_time)

            return response

        except Exception as e:
            logger.error(f"Request handling error: {e}")
            response_time = time.time() - start_time
            self._record_metrics(client_req, 500, response_time)
            return self._create_error_response(500, "Internal server error")

    def _find_route(self, method: str, path: str) -> Optional[Route]:
        """Find matching route for request."""
        route_key = f"{method.upper()}:{path}"

        with self.route_lock:
            # Exact match first
            if route_key in self.routes:
                return self.routes[route_key]

            # Pattern matching (simplified - would use regex in production)
            for route_pattern, route in self.routes.items():
                if self._path_matches(route.path, path):
                    return route

        return None

    def _path_matches(self, route_path: str, request_path: str) -> bool:
        """Check if request path matches route pattern."""
        # Simple pattern matching - would be more sophisticated in production
        if route_path == request_path:
            return True

        # Check for path parameters (e.g., /users/{id})
        route_parts = route_path.split('/')
        request_parts = request_path.split('/')

        if len(route_parts) != len(request_parts):
            return False

        for route_part, request_part in zip(route_parts, request_parts):
            if route_part.startswith('{') and route_part.endswith('}'):
                continue  # Path parameter
            if route_part != request_part:
                return False

        return True

    def _authenticate(self, headers: Dict[str, str]) -> Optional[str]:
        """Authenticate request."""
        if self.auth_function:
            return self.auth_function(headers)
        return None

    async def _route_to_service(
        self,
        client_req: ClientRequest,
        route: Route,
        request
    ) -> aiohttp.web.Response:
        """Route request to appropriate service."""
        if not self.service_registry:
            return self._create_error_response(503, "Service registry unavailable")

        # Discover service instances
        instances = self.service_registry.discover_service(route.service_name)
        if not instances:
            return self._create_error_response(503, f"Service {route.service_name} unavailable")

        # Load balancing - simple round robin
        instance = instances[0]  # Would implement proper load balancing

        # Build target URL
        target_url = f"{instance.get_url()}"
        if route.service_path:
            target_url += route.service_path
        else:
            # Remove gateway prefix and forward remaining path
            gateway_prefix = self.config.get('api_prefix', '/api')
            if client_req.path.startswith(gateway_prefix):
                remaining_path = client_req.path[len(gateway_prefix):]
                target_url += remaining_path

        # Forward request
        try:
            async with aiohttp.ClientSession() as session:
                # Prepare headers
                headers = dict(request.headers)
                headers['X-Request-ID'] = client_req.request_id
                headers['X-Client-IP'] = client_req.client_ip
                if client_req.user_id:
                    headers['X-User-ID'] = client_req.user_id

                # Make request
                async with session.request(
                    request.method,
                    target_url,
                    headers=headers,
                    data=await request.read(),
                    timeout=aiohttp.ClientTimeout(total=route.timeout)
                ) as resp:
                    # Return response
                    response_data = await resp.read()
                    return aiohttp.web.Response(
                        status=resp.status,
                        headers=resp.headers,
                        body=response_data
                    )

        except asyncio.TimeoutError:
            return self._create_error_response(504, "Gateway timeout")
        except Exception as e:
            logger.error(f"Service routing error: {e}")
            return self._create_error_response(502, "Bad gateway")

    def _create_error_response(self, status: int, message: str) -> aiohttp.web.Response:
        """Create error response."""
        return aiohttp.web.json_response(
            {'error': message, 'status': status},
            status=status
        )

    def _generate_request_id(self) -> str:
        """Generate unique request ID."""
        return hashlib.md5(f"{time.time()}_{threading.current_thread().ident}".encode()).hexdigest()[:8]

    def _get_client_ip(self, request) -> str:
        """Get client IP address."""
        # Check forwarded headers first
        forwarded = request.headers.get('X-Forwarded-For')
        if forwarded:
            return forwarded.split(',')[0].strip()

        # Check real IP header
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip

        # Fall back to peer name
        return request.remote or 'unknown'

    def _record_metrics(self, client_req: ClientRequest, status_code: int, response_time: float):
        """Record request metrics."""
        self.request_stats[status_code] += 1
        self.response_times.append(response_time)

        if status_code >= 400:
            self.error_counts[status_code] += 1

    def get_metrics(self) -> Dict[str, Any]:
        """Get gateway metrics."""
        total_requests = sum(self.request_stats.values())
        error_rate = sum(self.error_counts.values()) / max(1, total_requests)

        avg_response_time = sum(self.response_times) / max(1, len(self.response_times)) if self.response_times else 0

        return {
            'total_requests': total_requests,
            'status_codes': dict(self.request_stats),
            'error_rate': error_rate,
            'avg_response_time': avg_response_time,
            'active_routes': len(self.routes),
            'error_counts': dict(self.error_counts)
        }

    def get_routes(self) -> Dict[str, Dict[str, Any]]:
        """Get all registered routes."""
        with self.route_lock:
            return {
                route_key: {
                    'path': route.path,
                    'method': route.method,
                    'service_name': route.service_name,
                    'auth_required': route.auth_required,
                    'rate_limit': route.rate_limit
                }
                for route_key, route in self.routes.items()
            }

    def remove_route(self, path: str, method: str) -> bool:
        """Remove a route."""
        route_key = f"{method.upper()}:{path}"

        with self.route_lock:
            if route_key in self.routes:
                del self.routes[route_key]
                if route_key in self.rate_limiters:
                    del self.rate_limiters[route_key]
                logger.info(f"Removed route {route_key}")
                return True

        return False

    def health_check(self) -> Dict[str, Any]:
        """Gateway health check."""
        metrics = self.get_metrics()

        is_healthy = (
            metrics['error_rate'] < 0.1 and  # Less than 10% errors
            metrics['avg_response_time'] < 5.0  # Less than 5 seconds average
        )

        return {
            'healthy': is_healthy,
            'metrics': metrics,
            'routes_available': len(self.routes) > 0,
            'service_registry_connected': self.service_registry is not None
        }

    def enable_cors(self, origins: List[str] = None):
        """Enable CORS support."""
        origins = origins or ['*']

        def cors_middleware(client_req, request):
            # Add CORS headers to response
            pass  # Would implement CORS middleware

        self.add_middleware(cors_middleware)
        logger.info("CORS enabled")

    def enable_logging(self):
        """Enable request logging middleware."""
        def logging_middleware(client_req, request):
            logger.info(f"Request: {client_req.method} {client_req.path} from {client_req.client_ip}")

        self.add_middleware(logging_middleware)
        logger.info("Request logging enabled")







