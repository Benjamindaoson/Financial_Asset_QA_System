"""
Load Balancer for GraphRAG.

This module provides intelligent load balancing across distributed workers,
optimizing resource utilization and response times.
"""

import logging
from typing import Dict, List, Any, Optional, Callable, Union
import time
import random
import threading
import statistics
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class Worker:
    """Represents a worker node in the distributed system."""
    worker_id: str
    host: str
    port: int
    capabilities: List[str]
    status: str = 'active'
    last_heartbeat: float = None
    load_factor: float = 0.0
    response_time: float = 0.0
    success_rate: float = 1.0
    active_tasks: int = 0
    max_concurrency: int = 10

    def __post_init__(self):
        if self.last_heartbeat is None:
            self.last_heartbeat = time.time()

    def is_healthy(self) -> bool:
        """Check if worker is healthy."""
        return (
            self.status == 'active' and
            time.time() - self.last_heartbeat < 30.0 and  # 30 second timeout
            self.success_rate > 0.8  # 80% success rate
        )

    def can_accept_task(self, task_type: str) -> bool:
        """Check if worker can accept a specific task type."""
        return (
            self.is_healthy() and
            self.active_tasks < self.max_concurrency and
            (task_type in self.capabilities or 'general' in self.capabilities)
        )


class LoadBalancer:
    """
    Intelligent load balancer with multiple strategies and health monitoring.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize load balancer.

        Args:
            config: Configuration for load balancing
        """
        self.config = config or {}

        # Balancing strategies
        self.strategy = self.config.get('strategy', 'round_robin')
        self.available_strategies = {
            'round_robin': self._round_robin_select,
            'least_loaded': self._least_loaded_select,
            'weighted_random': self._weighted_random_select,
            'response_time': self._response_time_select,
            'adaptive': self._adaptive_select
        }

        # Worker management
        self.workers: Dict[str, Worker] = {}
        self.worker_lock = threading.Lock()
        self.round_robin_index = 0

        # Task routing
        self.task_routes = defaultdict(list)  # task_type -> [worker_ids]
        self.task_history = defaultdict(list)  # task_id -> [(worker_id, timestamp, success)]

        # Performance tracking
        self.performance_stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'avg_response_time': 0.0,
            'worker_utilization': {}
        }

        # Health monitoring
        self.health_check_interval = self.config.get('health_check_interval', 10.0)
        self.health_monitor_thread = None
        self.monitoring_active = False

        logger.info(f"Load balancer initialized with {self.strategy} strategy")

    def register_worker(
        self,
        worker_id: str,
        host: str,
        port: int,
        capabilities: List[str],
        max_concurrency: int = 10
    ) -> bool:
        """
        Register a new worker.

        Args:
            worker_id: Unique worker identifier
            host: Worker host
            port: Worker port
            capabilities: List of task types the worker can handle
            max_concurrency: Maximum concurrent tasks

        Returns:
            Success status
        """
        with self.worker_lock:
            if worker_id in self.workers:
                logger.warning(f"Worker {worker_id} already registered, updating")
                self.workers[worker_id].status = 'active'
                self.workers[worker_id].last_heartbeat = time.time()
                return True

            worker = Worker(
                worker_id=worker_id,
                host=host,
                port=port,
                capabilities=capabilities,
                max_concurrency=max_concurrency
            )

            self.workers[worker_id] = worker

            # Update task routing
            for capability in capabilities:
                self.task_routes[capability].append(worker_id)

            logger.info(f"Registered worker {worker_id} at {host}:{port} with capabilities: {capabilities}")

        return True

    def unregister_worker(self, worker_id: str) -> bool:
        """
        Unregister a worker.

        Args:
            worker_id: Worker ID to unregister

        Returns:
            Success status
        """
        with self.worker_lock:
            if worker_id not in self.workers:
                return False

            worker = self.workers[worker_id]
            worker.status = 'inactive'

            # Remove from task routing
            for capability in worker.capabilities:
                if worker_id in self.task_routes[capability]:
                    self.task_routes[capability].remove(worker_id)

            logger.info(f"Unregistered worker {worker_id}")

        return True

    def select_worker(self, task_type: str = 'general', task_data: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Select an appropriate worker for a task.

        Args:
            task_type: Type of task
            task_data: Additional task data for intelligent routing

        Returns:
            Selected worker ID or None if no suitable worker found
        """
        with self.worker_lock:
            available_workers = self._get_available_workers(task_type)

            if not available_workers:
                logger.warning(f"No available workers for task type: {task_type}")
                return None

            # Use configured strategy
            selector = self.available_strategies.get(self.strategy, self._round_robin_select)

            try:
                selected_worker = selector(available_workers, task_type, task_data)
                if selected_worker:
                    self.workers[selected_worker].active_tasks += 1
                    self.performance_stats['total_requests'] += 1

                return selected_worker

            except Exception as e:
                logger.error(f"Worker selection failed: {e}")
                # Fallback to round robin
                return self._round_robin_select(available_workers, task_type, task_data)

    def _get_available_workers(self, task_type: str) -> List[Worker]:
        """Get workers available for a task type."""
        available = []

        for worker in self.workers.values():
            if worker.can_accept_task(task_type):
                available.append(worker)

        return available

    def _round_robin_select(self, workers: List[Worker], task_type: str, task_data: Optional[Dict[str, Any]]) -> Optional[str]:
        """Round-robin worker selection."""
        if not workers:
            return None

        # Simple round-robin
        selected_worker = workers[self.round_robin_index % len(workers)]
        self.round_robin_index += 1

        return selected_worker.worker_id

    def _least_loaded_select(self, workers: List[Worker], task_type: str, task_data: Optional[Dict[str, Any]]) -> Optional[str]:
        """Select least loaded worker."""
        if not workers:
            return None

        # Sort by load factor (active_tasks / max_concurrency)
        sorted_workers = sorted(workers, key=lambda w: w.active_tasks / max(1, w.max_concurrency))

        return sorted_workers[0].worker_id

    def _weighted_random_select(self, workers: List[Worker], task_type: str, task_data: Optional[Dict[str, Any]]) -> Optional[str]:
        """Weighted random selection based on worker performance."""
        if not workers:
            return None

        # Calculate weights based on success rate and inverse load
        weights = []
        for worker in workers:
            # Weight = success_rate * (1 - load_factor)
            load_factor = worker.active_tasks / max(1, worker.max_concurrency)
            weight = worker.success_rate * (1 - load_factor)
            weights.append(max(0.1, weight))  # Minimum weight

        # Normalize weights
        total_weight = sum(weights)
        if total_weight == 0:
            return random.choice(workers).worker_id

        normalized_weights = [w / total_weight for w in weights]

        # Weighted random selection
        r = random.random()
        cumulative = 0
        for i, weight in enumerate(normalized_weights):
            cumulative += weight
            if r <= cumulative:
                return workers[i].worker_id

        return workers[-1].worker_id

    def _response_time_select(self, workers: List[Worker], task_type: str, task_data: Optional[Dict[str, Any]]) -> Optional[str]:
        """Select worker with best response time."""
        if not workers:
            return None

        # Sort by response time (ascending)
        sorted_workers = sorted(workers, key=lambda w: w.response_time)

        return sorted_workers[0].worker_id

    def _adaptive_select(self, workers: List[Worker], task_type: str, task_data: Optional[Dict[str, Any]]) -> Optional[str]:
        """Adaptive selection based on multiple factors."""
        if not workers:
            return None

        # Calculate composite score for each worker
        scores = []
        for worker in workers:
            score = 0.0

            # Response time score (lower is better)
            rt_score = 1.0 / (1.0 + worker.response_time)
            score += 0.4 * rt_score

            # Success rate score
            score += 0.3 * worker.success_rate

            # Load score (lower load is better)
            load_factor = worker.active_tasks / max(1, worker.max_concurrency)
            load_score = 1.0 - load_factor
            score += 0.3 * load_score

            scores.append(score)

        # Select worker with highest score
        best_index = scores.index(max(scores))
        return workers[best_index].worker_id

    def report_task_completion(
        self,
        task_id: str,
        worker_id: str,
        success: bool,
        response_time: float,
        task_type: str = 'general'
    ):
        """
        Report task completion for performance tracking.

        Args:
            task_id: Task identifier
            worker_id: Worker that executed the task
            success: Whether task was successful
            response_time: Task response time
            task_type: Type of task
        """
        with self.worker_lock:
            if worker_id not in self.workers:
                logger.warning(f"Unknown worker {worker_id} reported task completion")
                return

            worker = self.workers[worker_id]

            # Update worker stats
            worker.active_tasks = max(0, worker.active_tasks - 1)
            worker.last_heartbeat = time.time()

            if success:
                self.performance_stats['successful_requests'] += 1
                # Update response time (exponential moving average)
                alpha = 0.1
                worker.response_time = alpha * response_time + (1 - alpha) * worker.response_time

                # Update success rate
                total_tasks = len([h for h in self.task_history[task_id] if h[0] == worker_id])
                successful_tasks = len([h for h in self.task_history[task_id]
                                      if h[0] == worker_id and h[2]])
                worker.success_rate = successful_tasks / max(1, total_tasks)

            else:
                self.performance_stats['failed_requests'] += 1

            # Record task history
            self.task_history[task_id].append((worker_id, time.time(), success))

            # Update overall stats
            total_requests = self.performance_stats['total_requests']
            if total_requests > 0:
                success_rate = self.performance_stats['successful_requests'] / total_requests
                self.performance_stats['avg_response_time'] = (
                    self.performance_stats['avg_response_time'] * (total_requests - 1) +
                    response_time
                ) / total_requests

    def update_worker_heartbeat(self, worker_id: str):
        """Update worker heartbeat timestamp."""
        with self.worker_lock:
            if worker_id in self.workers:
                self.workers[worker_id].last_heartbeat = time.time()

    def get_worker_stats(self, worker_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get worker statistics.

        Args:
            worker_id: Specific worker ID, or None for all workers

        Returns:
            Worker statistics
        """
        with self.worker_lock:
            if worker_id:
                worker = self.workers.get(worker_id)
                if not worker:
                    return {'error': 'Worker not found'}

                return {
                    'worker_id': worker.worker_id,
                    'status': worker.status,
                    'load_factor': worker.load_factor,
                    'response_time': worker.response_time,
                    'success_rate': worker.success_rate,
                    'active_tasks': worker.active_tasks,
                    'max_concurrency': worker.max_concurrency,
                    'capabilities': worker.capabilities,
                    'last_heartbeat': worker.last_heartbeat,
                    'healthy': worker.is_healthy()
                }

            # All workers
            worker_stats = {}
            for wid, worker in self.workers.items():
                worker_stats[wid] = {
                    'status': worker.status,
                    'load_factor': worker.active_tasks / max(1, worker.max_concurrency),
                    'response_time': worker.response_time,
                    'success_rate': worker.success_rate,
                    'active_tasks': worker.active_tasks,
                    'healthy': worker.is_healthy()
                }

            return worker_stats

    def get_load_balancer_stats(self) -> Dict[str, Any]:
        """Get load balancer statistics."""
        with self.worker_lock:
            total_workers = len(self.workers)
            active_workers = sum(1 for w in self.workers.values() if w.status == 'active')
            healthy_workers = sum(1 for w in self.workers.values() if w.is_healthy())

            worker_utilization = {}
            for worker_id, worker in self.workers.items():
                worker_utilization[worker_id] = {
                    'utilization': worker.active_tasks / max(1, worker.max_concurrency),
                    'status': worker.status,
                    'healthy': worker.is_healthy()
                }

            return {
                'total_workers': total_workers,
                'active_workers': active_workers,
                'healthy_workers': healthy_workers,
                'performance_stats': self.performance_stats,
                'worker_utilization': worker_utilization,
                'current_strategy': self.strategy,
                'task_routes': dict(self.task_routes)
            }

    def change_strategy(self, new_strategy: str) -> bool:
        """
        Change load balancing strategy.

        Args:
            new_strategy: New strategy name

        Returns:
            Success status
        """
        if new_strategy not in self.available_strategies:
            logger.error(f"Unknown strategy: {new_strategy}")
            return False

        self.strategy = new_strategy
        logger.info(f"Changed load balancing strategy to: {new_strategy}")
        return True

    def start_health_monitoring(self):
        """Start health monitoring thread."""
        if self.monitoring_active:
            return

        self.monitoring_active = True
        self.health_monitor_thread = threading.Thread(
            target=self._health_monitor_loop,
            name='health-monitor',
            daemon=True
        )
        self.health_monitor_thread.start()

        logger.info("Health monitoring started")

    def stop_health_monitoring(self):
        """Stop health monitoring."""
        self.monitoring_active = False
        if self.health_monitor_thread:
            self.health_monitor_thread.join(timeout=5.0)

        logger.info("Health monitoring stopped")

    def _health_monitor_loop(self):
        """Health monitoring loop."""
        while self.monitoring_active:
            try:
                time.sleep(self.health_check_interval)

                with self.worker_lock:
                    current_time = time.time()
                    unhealthy_workers = []

                    for worker_id, worker in self.workers.items():
                        if not worker.is_healthy():
                            unhealthy_workers.append(worker_id)
                            logger.warning(f"Unhealthy worker detected: {worker_id}")

                            # Mark as inactive if too many failures
                            if worker.success_rate < 0.5:
                                worker.status = 'inactive'
                                logger.error(f"Worker {worker_id} marked inactive due to low success rate")

                    if unhealthy_workers:
                        logger.info(f"Found {len(unhealthy_workers)} unhealthy workers")

            except Exception as e:
                logger.error(f"Health monitoring error: {e}")

    def redistribute_load(self) -> Dict[str, Any]:
        """
        Redistribute load when workers become unavailable.

        Returns:
            Redistribution results
        """
        with self.worker_lock:
            results = {
                'redistributed_tasks': 0,
                'affected_workers': [],
                'new_assignments': []
            }

            # Find overloaded workers
            overloaded_workers = []
            for worker_id, worker in self.workers.items():
                if worker.active_tasks > worker.max_concurrency * 0.9:  # 90% capacity
                    overloaded_workers.append(worker_id)

            # Simple redistribution logic (in practice, would be more complex)
            if overloaded_workers:
                results['affected_workers'] = overloaded_workers
                # Would implement actual task redistribution here

            return results

    def get_optimal_worker_count(self) -> int:
        """
        Calculate optimal worker count based on current load.

        Returns:
            Recommended worker count
        """
        total_active_tasks = sum(w.active_tasks for w in self.workers.values())
        avg_tasks_per_worker = total_active_tasks / max(1, len(self.workers))

        # Target: 70-80% utilization per worker
        target_utilization = 0.75
        optimal_count = int(total_active_tasks / (target_utilization * 10))  # Assuming 10 max per worker

        return max(1, optimal_count)







