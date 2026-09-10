"""
Concurrency Manager for GraphRAG.

This module manages high concurrency operations with load balancing,
resource allocation, and distributed processing capabilities.
"""

import logging
from typing import Dict, List, Any, Optional, Callable, Union
import time
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import queue
import psutil
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """Task priority levels."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Represents a concurrent task."""
    task_id: str
    priority: TaskPriority
    func: Callable
    args: tuple
    kwargs: dict
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = None
    started_at: float = None
    completed_at: float = None
    result: Any = None
    error: Exception = None
    worker_id: str = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()


class ConcurrencyManager:
    """
    High-performance concurrency manager with adaptive scaling.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize concurrency manager.

        Args:
            config: Configuration for concurrency management
        """
        self.config = config or {}

        # Performance targets
        self.target_qps = self.config.get('target_qps', 1000)
        self.max_concurrent_tasks = self.config.get('max_concurrent_tasks', 100)
        self.task_timeout = self.config.get('task_timeout', 30.0)  # seconds

        # Resource limits
        self.max_cpu_usage = self.config.get('max_cpu_usage', 0.8)
        self.max_memory_usage = self.config.get('max_memory_usage', 0.8)
        self.max_threads = self.config.get('max_threads', 50)

        # Executors
        self.thread_executor = None
        self.process_executor = None
        self.async_loop = None

        # Task management
        self.task_queue = queue.PriorityQueue()
        self.running_tasks = {}
        self.completed_tasks = {}
        self.task_counter = 0
        self.task_lock = threading.Lock()

        # Worker management
        self.workers = {}
        self.worker_counter = 0

        # Monitoring
        self.metrics = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'avg_response_time': 0.0,
            'current_concurrency': 0,
            'peak_concurrency': 0
        }

        # Control flags
        self.running = False
        self.adaptive_scaling = True

        # Initialize executors
        self._init_executors()

        logger.info("Concurrency manager initialized")

    def _init_executors(self):
        """Initialize thread and process executors."""
        # Thread pool for I/O bound tasks
        self.thread_executor = ThreadPoolExecutor(
            max_workers=self.max_threads,
            thread_name_prefix='graphrag-worker'
        )

        # Process pool for CPU intensive tasks (optional)
        if self.config.get('use_process_pool', False):
            self.process_executor = ProcessPoolExecutor(
                max_workers=max(1, psutil.cpu_count() // 2)
            )

        # Async event loop
        try:
            self.async_loop = asyncio.new_event_loop()
        except Exception as e:
            logger.warning(f"Failed to create async loop: {e}")

    def start(self):
        """Start the concurrency manager."""
        self.running = True

        # Start task dispatcher thread
        dispatcher_thread = threading.Thread(
            target=self._task_dispatcher,
            name='task-dispatcher',
            daemon=True
        )
        dispatcher_thread.start()

        # Start monitoring thread
        monitor_thread = threading.Thread(
            target=self._monitor_resources,
            name='resource-monitor',
            daemon=True
        )
        monitor_thread.start()

        logger.info("Concurrency manager started")

    def stop(self):
        """Stop the concurrency manager."""
        self.running = False

        # Shutdown executors
        if self.thread_executor:
            self.thread_executor.shutdown(wait=True)

        if self.process_executor:
            self.process_executor.shutdown(wait=True)

        # Cancel pending tasks
        with self.task_lock:
            while not self.task_queue.empty():
                try:
                    _, task = self.task_queue.get_nowait()
                    task.status = TaskStatus.CANCELLED
                except queue.Empty:
                    break

        logger.info("Concurrency manager stopped")

    def submit_task(
        self,
        func: Callable,
        *args,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: Optional[float] = None,
        **kwargs
    ) -> str:
        """
        Submit a task for concurrent execution.

        Args:
            func: Function to execute
            *args: Positional arguments
            priority: Task priority
            timeout: Task timeout
            **kwargs: Keyword arguments

        Returns:
            Task ID
        """
        task_id = f"task_{self.task_counter}"
        self.task_counter += 1

        task = Task(
            task_id=task_id,
            priority=priority,
            func=func,
            args=args,
            kwargs=kwargs
        )

        # Set custom timeout if provided
        if timeout:
            task.timeout = timeout

        # Add to queue
        with self.task_lock:
            self.task_queue.put((priority.value, task))
            self.metrics['total_tasks'] += 1

        logger.debug(f"Submitted task {task_id} with priority {priority.name}")

        return task_id

    def submit_batch(
        self,
        tasks: List[Dict[str, Any]],
        priority: TaskPriority = TaskPriority.NORMAL
    ) -> List[str]:
        """
        Submit multiple tasks as a batch.

        Args:
            tasks: List of task dictionaries with 'func', 'args', 'kwargs'
            priority: Batch priority

        Returns:
            List of task IDs
        """
        task_ids = []

        for task_info in tasks:
            func = task_info['func']
            args = task_info.get('args', ())
            kwargs = task_info.get('kwargs', {})
            task_priority = task_info.get('priority', priority)

            task_id = self.submit_task(func, *args, priority=task_priority, **kwargs)
            task_ids.append(task_id)

        logger.info(f"Submitted batch of {len(tasks)} tasks")

        return task_ids

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get status of a specific task.

        Args:
            task_id: Task ID

        Returns:
            Task status information
        """
        with self.task_lock:
            # Check running tasks
            if task_id in self.running_tasks:
                task = self.running_tasks[task_id]
            # Check completed tasks
            elif task_id in self.completed_tasks:
                task = self.completed_tasks[task_id]
            else:
                return {'status': 'not_found'}

        status_info = {
            'task_id': task.task_id,
            'status': task.status.value,
            'priority': task.priority.name,
            'created_at': task.created_at,
            'started_at': task.started_at,
            'completed_at': task.completed_at,
            'worker_id': task.worker_id
        }

        if task.status == TaskStatus.COMPLETED:
            status_info['result'] = task.result
        elif task.status == TaskStatus.FAILED:
            status_info['error'] = str(task.error)

        return status_info

    def wait_for_task(
        self,
        task_id: str,
        timeout: Optional[float] = None
    ) -> Optional[Any]:
        """
        Wait for a task to complete and return its result.

        Args:
            task_id: Task ID
            timeout: Maximum wait time

        Returns:
            Task result or None if timeout
        """
        start_time = time.time()
        poll_interval = 0.1

        while timeout is None or (time.time() - start_time) < timeout:
            status = self.get_task_status(task_id)

            if status['status'] == 'completed':
                return status.get('result')
            elif status['status'] in ['failed', 'cancelled']:
                error = status.get('error', 'Task failed')
                raise Exception(f"Task {task_id} failed: {error}")

            time.sleep(poll_interval)

        raise TimeoutError(f"Task {task_id} timed out after {timeout} seconds")

    def wait_for_batch(
        self,
        task_ids: List[str],
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Wait for multiple tasks to complete.

        Args:
            task_ids: List of task IDs
            timeout: Maximum wait time

        Returns:
            Batch completion results
        """
        start_time = time.time()
        results = {}
        completed_count = 0

        while completed_count < len(task_ids):
            if timeout and (time.time() - start_time) > timeout:
                break

            for task_id in task_ids:
                if task_id not in results:
                    status = self.get_task_status(task_id)
                    if status['status'] in ['completed', 'failed', 'cancelled']:
                        results[task_id] = status
                        completed_count += 1

            time.sleep(0.1)

        return {
            'completed': completed_count,
            'total': len(task_ids),
            'results': results,
            'timed_out': completed_count < len(task_ids)
        }

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a pending or running task.

        Args:
            task_id: Task ID

        Returns:
            True if cancelled successfully
        """
        with self.task_lock:
            # Check running tasks
            if task_id in self.running_tasks:
                task = self.running_tasks[task_id]
                task.status = TaskStatus.CANCELLED
                # Note: In practice, you'd need to implement actual cancellation
                # which is complex in Python threads
                return True

            # Check queue (this is simplified - actual implementation would need queue inspection)
            # For now, just mark as cancelled if found in completed tasks
            if task_id in self.completed_tasks:
                return False  # Too late to cancel

        return False

    def _task_dispatcher(self):
        """Task dispatcher thread."""
        while self.running:
            try:
                # Check resource availability
                if not self._can_accept_new_tasks():
                    time.sleep(0.1)
                    continue

                # Get next task from queue
                try:
                    priority_value, task = self.task_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                # Check if we can still run this task
                if not self.running:
                    task.status = TaskStatus.CANCELLED
                    continue

                # Submit to executor
                self._execute_task(task)

            except Exception as e:
                logger.error(f"Task dispatcher error: {e}")

    def _execute_task(self, task: Task):
        """Execute a task using appropriate executor."""
        task.status = TaskStatus.RUNNING
        task.started_at = time.time()

        with self.task_lock:
            self.running_tasks[task.task_id] = task
            self.metrics['current_concurrency'] = len(self.running_tasks)
            self.metrics['peak_concurrency'] = max(
                self.metrics['peak_concurrency'],
                self.metrics['current_concurrency']
            )

        # Determine execution method based on task characteristics
        if self._is_cpu_intensive(task):
            future = self.process_executor.submit(self._task_wrapper, task)
        else:
            future = self.thread_executor.submit(self._task_wrapper, task)

        # Add callback for completion
        future.add_done_callback(lambda f: self._task_completed(f, task))

    def _task_wrapper(self, task: Task) -> Any:
        """Wrapper for task execution with error handling."""
        try:
            # Set worker ID
            task.worker_id = f"worker_{threading.current_thread().ident}"

            # Execute task
            result = task.func(*task.args, **task.kwargs)
            return result

        except Exception as e:
            logger.error(f"Task {task.task_id} failed: {e}")
            raise e

    def _task_completed(self, future, task: Task):
        """Handle task completion."""
        task.completed_at = time.time()

        try:
            result = future.result()
            task.result = result
            task.status = TaskStatus.COMPLETED

            # Update metrics
            response_time = task.completed_at - task.started_at
            self.metrics['completed_tasks'] += 1
            self._update_response_time(response_time)

        except Exception as e:
            task.error = e
            task.status = TaskStatus.FAILED
            self.metrics['failed_tasks'] += 1

        # Move to completed tasks
        with self.task_lock:
            if task.task_id in self.running_tasks:
                del self.running_tasks[task.task_id]

            self.completed_tasks[task.task_id] = task

            # Clean up old completed tasks
            self._cleanup_completed_tasks()

    def _can_accept_new_tasks(self) -> bool:
        """Check if system can accept new tasks."""
        # Check concurrency limit
        if len(self.running_tasks) >= self.max_concurrent_tasks:
            return False

        # Check system resources
        cpu_usage = psutil.cpu_percent() / 100.0
        memory_usage = psutil.virtual_memory().percent / 100.0

        if cpu_usage > self.max_cpu_usage or memory_usage > self.max_memory_usage:
            return False

        return True

    def _is_cpu_intensive(self, task: Task) -> bool:
        """Determine if a task is CPU intensive."""
        # Simple heuristic based on function name or module
        func_name = getattr(task.func, '__name__', '').lower()
        module_name = getattr(task.func, '__module__', '').lower()

        cpu_keywords = ['compute', 'process', 'calculate', 'transform', 'encode', 'decode']
        cpu_modules = ['numpy', 'torch', 'tensorflow', 'sklearn']

        return (
            any(keyword in func_name for keyword in cpu_keywords) or
            any(module in module_name for module in cpu_modules)
        )

    def _update_response_time(self, response_time: float):
        """Update average response time metric."""
        current_avg = self.metrics['avg_response_time']
        total_completed = self.metrics['completed_tasks']

        # Exponential moving average
        alpha = 0.1
        self.metrics['avg_response_time'] = alpha * response_time + (1 - alpha) * current_avg

    def _cleanup_completed_tasks(self):
        """Clean up old completed tasks to prevent memory leaks."""
        max_completed_tasks = 1000

        if len(self.completed_tasks) > max_completed_tasks:
            # Remove oldest tasks
            sorted_tasks = sorted(
                self.completed_tasks.items(),
                key=lambda x: x[1].completed_at or 0
            )

            tasks_to_remove = sorted_tasks[:len(sorted_tasks) - max_completed_tasks]
            for task_id, _ in tasks_to_remove:
                del self.completed_tasks[task_id]

    def _monitor_resources(self):
        """Monitor system resources and adjust concurrency."""
        while self.running:
            try:
                time.sleep(5.0)  # Monitor every 5 seconds

                # Get current resource usage
                cpu_usage = psutil.cpu_percent()
                memory_usage = psutil.virtual_memory().percent
                disk_usage = psutil.disk_usage('/').percent

                # Log resource status
                logger.debug(f"Resources - CPU: {cpu_usage}%, Memory: {memory_usage}%, Disk: {disk_usage}%")

                # Adaptive scaling
                if self.adaptive_scaling:
                    self._adjust_concurrency(cpu_usage, memory_usage)

            except Exception as e:
                logger.error(f"Resource monitoring error: {e}")

    def _adjust_concurrency(self, cpu_usage: float, memory_usage: float):
        """Adjust concurrency based on resource usage."""
        # Simple adaptive scaling logic
        if cpu_usage > 85 or memory_usage > 85:
            # Reduce concurrency
            new_max = max(10, self.max_concurrent_tasks - 5)
            if new_max != self.max_concurrent_tasks:
                self.max_concurrent_tasks = new_max
                logger.info(f"Reduced max concurrency to {new_max}")

        elif cpu_usage < 50 and memory_usage < 50:
            # Increase concurrency
            new_max = min(200, self.max_concurrent_tasks + 2)
            if new_max != self.max_concurrent_tasks:
                self.max_concurrent_tasks = new_max
                logger.info(f"Increased max concurrency to {new_max}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get concurrency metrics."""
        with self.task_lock:
            metrics = self.metrics.copy()
            metrics.update({
                'pending_tasks': self.task_queue.qsize(),
                'running_tasks': len(self.running_tasks),
                'completed_tasks_count': len(self.completed_tasks),
                'active_workers': len(self.workers)
            })

        return metrics

    def get_queue_status(self) -> Dict[str, Any]:
        """Get task queue status."""
        with self.task_lock:
            # Count tasks by priority (simplified - actual implementation would inspect queue)
            status = {
                'queue_size': self.task_queue.qsize(),
                'running_count': len(self.running_tasks),
                'pending_by_priority': {
                    'critical': 0,  # Would need queue inspection
                    'high': 0,
                    'normal': 0,
                    'low': 0
                }
            }

        return status

    def scale_workers(self, target_count: int):
        """Scale the number of worker threads."""
        if self.thread_executor:
            # Note: ThreadPoolExecutor doesn't support dynamic scaling
            # In practice, you'd implement a custom thread pool
            logger.info(f"Worker scaling requested: target={target_count}")

    def enable_adaptive_scaling(self, enable: bool = True):
        """Enable or disable adaptive scaling."""
        self.adaptive_scaling = enable
        logger.info(f"Adaptive scaling {'enabled' if enable else 'disabled'}")

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the concurrency system."""
        metrics = self.get_metrics()

        # Determine health based on metrics
        is_healthy = (
            metrics['failed_tasks'] / max(1, metrics['total_tasks']) < 0.1 and  # < 10% failure rate
            metrics['current_concurrency'] < self.max_concurrent_tasks * 1.2    # Not overloaded
        )

        return {
            'healthy': is_healthy,
            'metrics': metrics,
            'last_check': time.time()
        }







