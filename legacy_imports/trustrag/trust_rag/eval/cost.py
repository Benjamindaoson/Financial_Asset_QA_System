"""
Cost Evaluation Metrics.

Tracks token usage, CPU, memory, disk I/O, and index size.
"""
import os
import psutil
from typing import Dict, List, Any, Optional
from pathlib import Path

from trust_rag.eval.schema import CostMetrics
from trust_rag.config import get_paths


class CostTracker:
    """Tracks cost and resource usage."""
    
    def __init__(self):
        self.token_usage: Dict[str, int] = {
            "total": 0,
            "prompt": 0,
            "completion": 0
        }
        self.cpu_samples: List[float] = []
        self.memory_samples: List[float] = []
        self.disk_io_start: Optional[Dict[str, int]] = None
        self.process = psutil.Process()
    
    def start(self):
        """Start tracking."""
        self.disk_io_start = self.process.io_counters()._asdict()
    
    def record_tokens(self, prompt_tokens: int = 0, completion_tokens: int = 0):
        """Record token usage."""
        self.token_usage["prompt"] += prompt_tokens
        self.token_usage["completion"] += completion_tokens
        self.token_usage["total"] += prompt_tokens + completion_tokens
    
    def sample_resources(self):
        """Sample current resource usage."""
        try:
            cpu_percent = self.process.cpu_percent(interval=0.1)
            memory_info = self.process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            self.cpu_samples.append(cpu_percent)
            self.memory_samples.append(memory_mb)
        except Exception:
            pass
    
    def get_disk_io(self) -> Dict[str, float]:
        """Get disk I/O in MB."""
        if not self.disk_io_start:
            return {"read_mb": 0.0, "write_mb": 0.0}
        
        try:
            current_io = self.process.io_counters()._asdict()
            read_bytes = current_io.get("read_bytes", 0) - self.disk_io_start.get("read_bytes", 0)
            write_bytes = current_io.get("write_bytes", 0) - self.disk_io_start.get("write_bytes", 0)
            
            return {
                "read_mb": read_bytes / 1024 / 1024,
                "write_mb": write_bytes / 1024 / 1024
            }
        except Exception:
            return {"read_mb": 0.0, "write_mb": 0.0}
    
    def get_index_size_mb(self) -> float:
        """Get index size in MB."""
        try:
            ingestion_dir = get_paths().ingestion_dir
            total_size = 0
            
            for root, dirs, files in os.walk(ingestion_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        total_size += os.path.getsize(file_path)
                    except Exception:
                        pass
            
            return total_size / 1024 / 1024
        except Exception:
            return 0.0
    
    def calculate_token_cost_usd(self, model: str = "gpt-4") -> float:
        """
        Calculate token cost in USD.
        
        Args:
            model: Model name (default: gpt-4)
            
        Returns:
            Cost in USD
        """
        # Pricing per 1K tokens (as of 2024)
        pricing = {
            "gpt-4": {"prompt": 0.03, "completion": 0.06},
            "gpt-3.5-turbo": {"prompt": 0.0015, "completion": 0.002},
            "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03}
        }
        
        model_pricing = pricing.get(model, pricing["gpt-4"])
        
        prompt_cost = (self.token_usage["prompt"] / 1000) * model_pricing["prompt"]
        completion_cost = (self.token_usage["completion"] / 1000) * model_pricing["completion"]
        
        return prompt_cost + completion_cost
    
    def to_cost_metrics(
        self,
        num_queries: int = 1,
        num_pages: int = 0,
        model: str = "gpt-4"
    ) -> CostMetrics:
        """
        Convert to CostMetrics.
        
        Args:
            num_queries: Number of queries processed
            num_pages: Number of pages ingested
            model: LLM model name
            
        Returns:
            CostMetrics instance
        """
        disk_io = self.get_disk_io()
        
        avg_cpu = sum(self.cpu_samples) / len(self.cpu_samples) if self.cpu_samples else 0.0
        peak_memory = max(self.memory_samples) if self.memory_samples else 0.0
        avg_memory = sum(self.memory_samples) / len(self.memory_samples) if self.memory_samples else 0.0
        
        # Estimate CPU time (rough approximation)
        total_cpu_ms = avg_cpu * 100  # Rough estimate
        
        token_cost = self.calculate_token_cost_usd(model)
        
        return CostMetrics(
            total_tokens=self.token_usage["total"],
            prompt_tokens=self.token_usage["prompt"],
            completion_tokens=self.token_usage["completion"],
            token_cost_usd=token_cost,
            total_cpu_ms=total_cpu_ms,
            total_mem_mb=avg_memory * num_queries,
            peak_mem_mb=peak_memory,
            disk_read_mb=disk_io["read_mb"],
            disk_write_mb=disk_io["write_mb"],
            index_size_mb=self.get_index_size_mb(),
            cost_per_query_usd=token_cost / num_queries if num_queries > 0 else 0.0,
            cost_per_page_usd=token_cost / num_pages if num_pages > 0 else 0.0,
            cpu_per_query_ms=total_cpu_ms / num_queries if num_queries > 0 else 0.0,
            mem_per_query_mb=avg_memory
        )


# Global cost tracker
_cost_tracker: Optional[CostTracker] = None


def get_cost_tracker() -> CostTracker:
    """Get or create global cost tracker."""
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = CostTracker()
        _cost_tracker.start()
    return _cost_tracker

