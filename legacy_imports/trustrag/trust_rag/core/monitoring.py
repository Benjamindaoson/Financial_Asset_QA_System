"""
Performance Monitoring and Metrics Collection.

Tracks system performance, resource usage, and operation timings.
"""
import time
import logging
import psutil
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from datetime import datetime
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


@dataclass
class OperationMetrics:
    """Metrics for a single operation."""
    operation_name: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def finish(self, success: bool = True, error: Optional[str] = None):
        """Mark operation as finished."""
        self.end_time = time.perf_counter()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.success = success
        self.error = error
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "operation": self.operation_name,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error": self.error,
            "metadata": self.metadata,
            "timestamp": datetime.fromtimestamp(self.start_time).isoformat()
        }


@dataclass
class SystemMetrics:
    """System-wide resource metrics."""
    timestamp: str
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    disk_usage_percent: Optional[float] = None
    active_operations: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class PerformanceMonitor:
    """
    Performance monitoring and metrics collection.
    
    Tracks:
    - Operation timings
    - System resource usage
    - Error rates
    - Throughput
    """
    
    def __init__(self, log_dir: Optional[str] = None):
        """
        Initialize performance monitor.
        
        Args:
            log_dir: Directory for metrics logs (optional)
        """
        self.log_dir = log_dir
        self._active_operations: Dict[str, OperationMetrics] = {}
        self._completed_operations: List[OperationMetrics] = []
        self._operation_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "count": 0,
            "total_duration_ms": 0.0,
            "success_count": 0,
            "error_count": 0,
            "min_duration_ms": float('inf'),
            "max_duration_ms": 0.0
        })
        self._system_metrics: List[SystemMetrics] = []
        
        # Start background monitoring if log_dir provided
        if self.log_dir:
            os.makedirs(self.log_dir, exist_ok=True)
    
    def start_operation(self, operation_name: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Start tracking an operation.
        
        Args:
            operation_name: Name of the operation
            metadata: Optional metadata
            
        Returns:
            Operation ID for tracking
        """
        op_id = f"{operation_name}_{int(time.time() * 1000)}"
        metrics = OperationMetrics(
            operation_name=operation_name,
            start_time=time.perf_counter(),
            metadata=metadata or {}
        )
        self._active_operations[op_id] = metrics
        return op_id
    
    def finish_operation(self, op_id: str, success: bool = True, error: Optional[str] = None):
        """
        Finish tracking an operation.
        
        Args:
            op_id: Operation ID from start_operation
            success: Whether operation succeeded
            error: Error message if failed
        """
        if op_id not in self._active_operations:
            logger.warning(f"Operation {op_id} not found in active operations")
            return
        
        metrics = self._active_operations.pop(op_id)
        metrics.finish(success=success, error=error)
        self._completed_operations.append(metrics)
        
        # Update statistics
        stats = self._operation_stats[metrics.operation_name]
        stats["count"] += 1
        stats["total_duration_ms"] += metrics.duration_ms or 0
        if success:
            stats["success_count"] += 1
        else:
            stats["error_count"] += 1
        stats["min_duration_ms"] = min(stats["min_duration_ms"], metrics.duration_ms or float('inf'))
        stats["max_duration_ms"] = max(stats["max_duration_ms"], metrics.duration_ms or 0)
        
        # Keep only last 1000 completed operations
        if len(self._completed_operations) > 1000:
            self._completed_operations = self._completed_operations[-1000:]
    
    def record_system_metrics(self):
        """Record current system resource usage."""
        try:
            process = psutil.Process(os.getpid())
            cpu_percent = process.cpu_percent(interval=0.1)
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            memory_percent = process.memory_percent()
            
            # Disk usage (for log directory if available)
            disk_usage_percent = None
            if self.log_dir:
                try:
                    disk = psutil.disk_usage(self.log_dir)
                    disk_usage_percent = disk.percent
                except:
                    pass
            
            metrics = SystemMetrics(
                timestamp=datetime.utcnow().isoformat(),
                cpu_percent=cpu_percent,
                memory_mb=memory_mb,
                memory_percent=memory_percent,
                disk_usage_percent=disk_usage_percent,
                active_operations=len(self._active_operations)
            )
            
            self._system_metrics.append(metrics)
            
            # Keep only last 100 system metrics
            if len(self._system_metrics) > 100:
                self._system_metrics = self._system_metrics[-100:]
                
        except Exception as e:
            logger.warning(f"Failed to record system metrics: {e}")
    
    def get_operation_stats(self, operation_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics for operations.
        
        Args:
            operation_name: Specific operation name, or None for all
            
        Returns:
            Statistics dictionary
        """
        if operation_name:
            # Default structure if not found
            default_stats = {
                "count": 0,
                "total_duration_ms": 0,
                "error_count": 0,
                "success_count": 0
            }
            stats = self._operation_stats.get(operation_name, default_stats)
            
            if stats.get("count", 0) > 0:
                stats["avg_duration_ms"] = stats["total_duration_ms"] / stats["count"]
                stats["success_rate"] = stats["success_count"] / stats["count"]
            else:
                stats["avg_duration_ms"] = 0
                stats["success_rate"] = 0
                
            return stats
        
        # Aggregate all operations
        result = {}
        for op_name, stats in self._operation_stats.items():
            if stats["count"] > 0:
                stats_copy = stats.copy()
                stats_copy["avg_duration_ms"] = stats["total_duration_ms"] / stats["count"]
                stats_copy["success_rate"] = stats["success_count"] / stats["count"]
                result[op_name] = stats_copy
        return result
    
    def get_system_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of system metrics."""
        if not self._system_metrics:
            return {}
        
        recent = self._system_metrics[-10:]  # Last 10 samples
        
        return {
            "sample_count": len(recent),
            "avg_cpu_percent": sum(m.cpu_percent for m in recent) / len(recent),
            "avg_memory_mb": sum(m.memory_mb for m in recent) / len(recent),
            "avg_memory_percent": sum(m.memory_percent for m in recent) / len(recent),
            "current_active_operations": len(self._active_operations),
            "latest": recent[-1].to_dict() if recent else None
        }
    
    def export_metrics(self, file_path: Optional[str] = None) -> str:
        """
        Export metrics to JSON file.
        
        Args:
            file_path: Output file path (optional)
            
        Returns:
            Path to exported file
        """
        if not file_path:
            if not self.log_dir:
                raise ValueError("No log_dir or file_path provided")
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            file_path = os.path.join(self.log_dir, f"metrics_{timestamp}.json")
        
        data = {
            "exported_at": datetime.utcnow().isoformat(),
            "operation_stats": self.get_operation_stats(),
            "system_metrics_summary": self.get_system_metrics_summary(),
            "recent_operations": [op.to_dict() for op in self._completed_operations[-100:]]
        }
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Exported metrics to {file_path}")
        return file_path
    
    def get_performance_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive performance report.
        
        Returns:
            Performance report dictionary
        """
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "operation_statistics": self.get_operation_stats(),
            "system_metrics": self.get_system_metrics_summary(),
            "active_operations": len(self._active_operations),
            "total_completed_operations": len(self._completed_operations),
            "recommendations": self._generate_recommendations()
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate performance optimization recommendations."""
        recommendations = []
        
        # Check for slow operations
        for op_name, stats in self._operation_stats.items():
            if stats["count"] > 0:
                avg_duration = stats["total_duration_ms"] / stats["count"]
                if avg_duration > 5000:  # > 5 seconds
                    recommendations.append(
                        f"Operation '{op_name}' average duration {avg_duration:.0f}ms, optimization recommended"
                    )
                
                # Check error rate
                if stats["count"] > 10:
                    error_rate = stats["error_count"] / stats["count"]
                    if error_rate > 0.1:  # > 10% error rate
                        recommendations.append(
                            f"Operation '{op_name}' error rate {error_rate*100:.1f}%, check recommended"
                        )
        
        # Check system resources
        if self._system_metrics:
            recent = self._system_metrics[-5:]
            avg_memory = sum(m.memory_percent for m in recent) / len(recent)
            if avg_memory > 80:
                recommendations.append("Memory usage exceeds 80%, optimization or expansion recommended")
            
            avg_cpu = sum(m.cpu_percent for m in recent) / len(recent)
            if avg_cpu > 90:
                recommendations.append("CPU usage exceeds 90%, possible performance bottleneck")
        
        return recommendations if recommendations else ["System performance normal"]


# Global monitor instance
_global_monitor: Optional[PerformanceMonitor] = None


def get_monitor() -> PerformanceMonitor:
    """Get or create global performance monitor."""
    global _global_monitor
    if _global_monitor is None:
        from trust_rag.config import get_paths
        log_dir = os.path.join(get_paths().logs_dir, "metrics")
        _global_monitor = PerformanceMonitor(log_dir=log_dir)
    return _global_monitor


def monitor_operation(operation_name: str):
    """
    Decorator to monitor a function's performance.
    
    Usage:
        @monitor_operation("query_processing")
        def process_query(query: str):
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            monitor = get_monitor()
            op_id = monitor.start_operation(operation_name, metadata={
                "function": func.__name__,
                "args_count": len(args),
                "kwargs_keys": list(kwargs.keys())
            })
            try:
                result = func(*args, **kwargs)
                monitor.finish_operation(op_id, success=True)
                return result
            except Exception as e:
                monitor.finish_operation(op_id, success=False, error=str(e))
                raise
        return wrapper
    return decorator



