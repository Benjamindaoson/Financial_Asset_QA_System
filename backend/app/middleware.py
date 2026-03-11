"""
中间件 - 请求性能监控和认证
Middleware - Request Performance Monitoring and Authentication
"""
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.monitoring import record_request


class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """性能监控中间件"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        success = True

        try:
            response = await call_next(request)
            if response.status_code >= 400:
                success = False
            return response
        except Exception as exc:
            success = False
            raise exc
        finally:
            duration = time.time() - start_time
            endpoint = f"{request.method} {request.url.path}"
            record_request(endpoint, duration, success)
