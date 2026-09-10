"""
Task Queue Production Tests with Fault Injection.

Tests Redis distributed task queue for:
- Normal enqueue/dequeue/ack operations
- Dead letter queue handling
- Redis connection failures
- Fault tolerance and graceful degradation
"""

import pytest
import time
import json
from unittest.mock import patch, MagicMock
from trust_rag.runtime.dispatcher.task_queue import Task, RedisTaskQueue


class TestTaskQueueNormalOperations:
    """Test normal task queue operations."""

    def test_enqueue_task(self):
        """Test task enqueueing."""
        # Mock Redis to avoid needing actual Redis instance
        with patch('trust_rag.runtime.dispatcher.task_queue.redis') as mock_redis:
            mock_client = MagicMock()
            mock_redis.from_url.return_value = mock_client
            mock_client.ping.return_value = True

            queue = RedisTaskQueue()
            task = Task(
                task_id="test_task_1",
                task_type="test",
                payload={"action": "test"},
                priority=5
            )

            result = queue.enqueue_task(task)

            assert result == "test_task_1"
            mock_client.zadd.assert_called_once()
            # Verify priority-based scoring
            call_args = mock_client.zadd.call_args
            assert call_args[1]['score'] == 5

    def test_dequeue_task(self):
        """Test task dequeuing with blocking pop."""
        with patch('trust_rag.runtime.dispatcher.task_queue.redis') as mock_redis:
            mock_client = MagicMock()
            mock_redis.from_url.return_value = mock_client
            mock_client.ping.return_value = True

            # Mock BZPOPMAX response
            task_data = {
                "task_id": "test_task_1",
                "task_type": "test",
                "payload": {"action": "test"},
                "priority": 5,
                "created_at": "2024-01-01T00:00:00",
                "timeout_seconds": 300,
                "max_retries": 3,
                "retry_count": 0,
                "tags": [],
                "metadata": {}
            }
            mock_client.bzpopmax.return_value = ("pending", json.dumps(task_data).encode(), 5.0)

            queue = RedisTaskQueue()
            task = queue.dequeue_task(timeout=10)

            assert task is not None
            assert task.task_id == "test_task_1"
            assert task.task_type == "test"
            assert task.payload == {"action": "test"}

    def test_task_completion(self):
        """Test successful task completion."""
        with patch('trust_rag.runtime.dispatcher.task_queue.redis') as mock_redis:
            mock_client = MagicMock()
            mock_redis.from_url.return_value = mock_client
            mock_client.ping.return_value = True

            queue = RedisTaskQueue()

            # First dequeue a task to set it up
            task_data = {
                "task_id": "test_task_1",
                "task_type": "test",
                "payload": {"action": "test"},
                "priority": 5,
                "created_at": "2024-01-01T00:00:00",
                "timeout_seconds": 300,
                "max_retries": 3,
                "retry_count": 0,
                "tags": [],
                "metadata": {}
            }
            mock_client.bzpopmax.return_value = ("pending", json.dumps(task_data).encode(), 5.0)

            task = queue.dequeue_task()
            assert task is not None

            # Complete the task
            result = queue.complete_task("test_task_1", {"result": "success"}, 1.5)

            # Verify task removed from processing and result stored
            mock_client.delete.assert_called()  # Remove from processing
            mock_client.zadd.assert_called()  # Add to completed queue

    def test_task_failure_retry(self):
        """Test task failure and retry logic."""
        with patch('trust_rag.runtime.dispatcher.task_queue.redis') as mock_redis:
            mock_client = MagicMock()
            mock_redis.from_url.return_value = mock_client
            mock_client.ping.return_value = True

            queue = RedisTaskQueue()

            # Set up task
            task_data = {
                "task_id": "test_task_1",
                "task_type": "test",
                "payload": {"action": "test"},
                "priority": 5,
                "created_at": "2024-01-01T00:00:00",
                "timeout_seconds": 300,
                "max_retries": 3,
                "retry_count": 0,
                "tags": [],
                "metadata": {}
            }
            mock_client.bzpopmax.return_value = ("pending", json.dumps(task_data).encode(), 5.0)

            task = queue.dequeue_task()
            assert task is not None

            # Fail the task
            queue.fail_task("test_task_1", "Test failure", 1.0)

            # Verify task removed from processing and re-enqueued with lower priority
            assert mock_client.delete.called  # Remove from processing
            # Should be re-enqueued (second zadd call)
            assert mock_client.zadd.call_count >= 2

    def test_dead_letter_queue(self):
        """Test dead letter queue for exhausted retries."""
        with patch('trust_rag.runtime.dispatcher.task_queue.redis') as mock_redis:
            mock_client = MagicMock()
            mock_redis.from_url.return_value = mock_client
            mock_client.ping.return_value = True

            queue = RedisTaskQueue()

            # Set up task with max retries reached
            task_data = {
                "task_id": "test_task_1",
                "task_type": "test",
                "payload": {"action": "test"},
                "priority": 5,
                "created_at": "2024-01-01T00:00:00",
                "timeout_seconds": 300,
                "max_retries": 3,
                "retry_count": 2,  # One retry left
                "tags": [],
                "metadata": {}
            }
            mock_client.bzpopmax.return_value = ("pending", json.dumps(task_data).encode(), 5.0)

            task = queue.dequeue_task()
            assert task is not None

            # Fail the task (should go to dead letter)
            queue.fail_task("test_task_1", "Final failure", 1.0)

            # Verify task went to dead letter queue
            dead_letter_calls = [call for call in mock_client.zadd.call_args_list
                               if call[1]['name'] == queue.dead_letter_queue]
            assert len(dead_letter_calls) > 0


class TestTaskQueueFaultTolerance:
    """Test task queue fault tolerance and graceful degradation."""

    def test_redis_connection_failure_init(self):
        """Test graceful handling of Redis connection failure during initialization."""
        with patch('trust_rag.runtime.dispatcher.task_queue.redis') as mock_redis:
            mock_redis.from_url.side_effect = Exception("Redis connection failed")

            with pytest.raises(Exception) as exc_info:
                RedisTaskQueue()

            assert "Redis connection failed" in str(exc_info.value)

    def test_enqueue_with_redis_failure(self):
        """Test enqueue behavior when Redis fails."""
        with patch('trust_rag.runtime.dispatcher.task_queue.redis') as mock_redis:
            mock_client = MagicMock()
            mock_redis.from_url.return_value = mock_client
            mock_client.ping.return_value = True
            mock_client.zadd.side_effect = Exception("Redis write failed")

            queue = RedisTaskQueue()
            task = Task(task_id="test", task_type="test", payload={})

            with pytest.raises(Exception) as exc_info:
                queue.enqueue_task(task)

            assert "Redis write failed" in str(exc_info.value)

    def test_dequeue_timeout(self):
        """Test dequeue timeout behavior."""
        with patch('trust_rag.runtime.dispatcher.task_queue.redis') as mock_redis:
            mock_client = MagicMock()
            mock_redis.from_url.return_value = mock_client
            mock_client.ping.return_value = True
            mock_client.bzpopmax.return_value = None  # Timeout

            queue = RedisTaskQueue()
            task = queue.dequeue_task(timeout=1)

            assert task is None

    def test_scheduled_task_processing(self):
        """Test processing of scheduled tasks."""
        with patch('trust_rag.runtime.dispatcher.task_queue.redis') as mock_redis:
            mock_client = MagicMock()
            mock_redis.from_url.return_value = mock_client
            mock_client.ping.return_value = True

            # Mock scheduled tasks ready to run
            scheduled_tasks = [
                json.dumps({
                    "task_id": "scheduled_1",
                    "task_type": "test",
                    "payload": {"scheduled": True},
                    "priority": 1,
                    "created_at": "2024-01-01T00:00:00",
                    "timeout_seconds": 300,
                    "max_retries": 3,
                    "retry_count": 0,
                    "tags": [],
                    "metadata": {}
                }).encode()
            ]
            mock_client.zrangebyscore.return_value = scheduled_tasks

            queue = RedisTaskQueue()
            queue._process_scheduled_tasks()

            # Verify scheduled task moved to pending
            pending_calls = [call for call in mock_client.zadd.call_args_list
                           if call[1]['name'] == queue.pending_queue]
            assert len(pending_calls) > 0

    def test_graceful_shutdown(self):
        """Test graceful shutdown with active task cleanup."""
        with patch('trust_rag.runtime.dispatcher.task_queue.redis') as mock_redis:
            mock_client = MagicMock()
            mock_redis.from_url.return_value = mock_client
            mock_client.ping.return_value = True

            queue = RedisTaskQueue()

            # Add an active task
            task = Task(task_id="active_task", task_type="test", payload={})
            queue.active_tasks["active_task"] = task

            # Shutdown
            queue.shutdown()

            # Verify active task was returned to queue
            assert len(queue.active_tasks) == 0
            mock_client.zadd.assert_called()  # Should re-enqueue active task

    def test_queue_stats_comprehensive(self):
        """Test comprehensive queue statistics."""
        with patch('trust_rag.runtime.dispatcher.task_queue.redis') as mock_redis:
            mock_client = MagicMock()
            mock_redis.from_url.return_value = mock_client
            mock_client.ping.return_value = True

            # Mock queue sizes and contents
            mock_client.zcard.side_effect = lambda key: {
                "trust_rag:pending": 5,
                "trust_rag:processing": 2,
                "trust_rag:scheduled": 1,
                "trust_rag:completed": 10,
                "trust_rag:dead_letter": 0
            }.get(key.split(':')[-1], 0)

            mock_client.zrange.return_value = [
                json.dumps({"priority": 1}).encode(),
                json.dumps({"priority": 3}).encode(),
                json.dumps({"priority": 1}).encode()
            ]

            queue = RedisTaskQueue()
            stats = queue.get_queue_stats()

            assert stats["pending_count"] == 5
            assert stats["processing_count"] == 2
            assert stats["completed_count"] == 10
            assert stats["dead_letter_count"] == 0
            assert "pending_priority_distribution" in stats


class TestTaskQueueIntegration:
    """Integration tests for task queue operations."""

    def test_full_task_lifecycle(self):
        """Test complete task lifecycle from enqueue to completion."""
        with patch('trust_rag.runtime.dispatcher.task_queue.redis') as mock_redis:
            mock_client = MagicMock()
            mock_redis.from_url.return_value = mock_client
            mock_client.ping.return_value = True

            queue = RedisTaskQueue()

            # 1. Enqueue task
            task = Task(
                task_id="lifecycle_test",
                task_type="integration_test",
                payload={"step": "lifecycle"},
                priority=2
            )
            queue.enqueue_task(task)

            # 2. Dequeue task
            task_data = {
                "task_id": "lifecycle_test",
                "task_type": "integration_test",
                "payload": {"step": "lifecycle"},
                "priority": 2,
                "created_at": "2024-01-01T00:00:00",
                "timeout_seconds": 300,
                "max_retries": 3,
                "retry_count": 0,
                "tags": [],
                "metadata": {}
            }
            mock_client.bzpopmax.return_value = ("pending", json.dumps(task_data).encode(), 2.0)

            dequeued_task = queue.dequeue_task()
            assert dequeued_task.task_id == "lifecycle_test"

            # 3. Complete task
            queue.complete_task("lifecycle_test", {"result": "success"}, 0.5)

            # Verify calls
            assert mock_client.zadd.call_count >= 2  # Enqueue + complete
            assert mock_client.delete.called  # Remove from processing

    def test_concurrent_worker_simulation(self):
        """Test multiple workers accessing queue simultaneously."""
        with patch('trust_rag.runtime.dispatcher.task_queue.redis') as mock_redis:
            mock_client = MagicMock()
            mock_redis.from_url.return_value = mock_client
            mock_client.ping.return_value = True

            # Create two queue instances (simulating two workers)
            queue1 = RedisTaskQueue()
            queue2 = RedisTaskQueue()

            queue1.worker_id = "worker_1"
            queue2.worker_id = "worker_2"

            # Both try to dequeue (simulate race condition)
            mock_client.bzpopmax.return_value = None  # No tasks available

            task1 = queue1.dequeue_task(timeout=1)
            task2 = queue2.dequeue_task(timeout=1)

            assert task1 is None
            assert task2 is None

            # Verify different worker IDs
            assert queue1.worker_id != queue2.worker_id
