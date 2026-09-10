"""
Service Registry for GraphRAG Microservices.

This module provides service discovery and registration capabilities
for the microservices architecture.
"""

import logging
from typing import Dict, List, Any, Optional, Callable, Union
import time
import threading
import json
from dataclasses import dataclass, asdict
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class ServiceInstance:
    """Represents a service instance."""
    service_id: str
    service_name: str
    host: str
    port: int
    protocol: str = 'http'
    version: str = '1.0.0'
    status: str = 'up'
    metadata: Dict[str, Any] = None
    registered_at: float = None
    last_heartbeat: float = None
    health_check_url: Optional[str] = None

    def __post_init__(self):
        if self.registered_at is None:
            self.registered_at = time.time()
        if self.last_heartbeat is None:
            self.last_heartbeat = time.time()
        if self.metadata is None:
            self.metadata = {}

    def is_healthy(self) -> bool:
        """Check if service instance is healthy."""
        return (
            self.status == 'up' and
            time.time() - self.last_heartbeat < 60.0  # 60 second timeout
        )

    def get_url(self) -> str:
        """Get service URL."""
        return f"{self.protocol}://{self.host}:{self.port}"

    def update_heartbeat(self):
        """Update heartbeat timestamp."""
        self.last_heartbeat = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class ServiceRegistry:
    """
    Service registry with automatic discovery and health monitoring.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize service registry.

        Args:
            config: Registry configuration
        """
        self.config = config or {}

        # Service storage
        self.services: Dict[str, List[ServiceInstance]] = defaultdict(list)
        self.service_lock = threading.Lock()

        # Registry settings
        self.heartbeat_timeout = self.config.get('heartbeat_timeout', 60.0)
        self.cleanup_interval = self.config.get('cleanup_interval', 30.0)
        self.max_instances_per_service = self.config.get('max_instances_per_service', 10)

        # Background tasks
        self.cleanup_thread = None
        self.running = False

        # Service metadata
        self.service_metadata = {}

        logger.info("Service registry initialized")

    def register_service(
        self,
        service_name: str,
        host: str,
        port: int,
        metadata: Optional[Dict[str, Any]] = None,
        protocol: str = 'http',
        version: str = '1.0.0',
        health_check_url: Optional[str] = None
    ) -> str:
        """
        Register a service instance.

        Args:
            service_name: Name of the service
            host: Service host
            port: Service port
            metadata: Service metadata
            protocol: Protocol (http, grpc, etc.)
            version: Service version
            health_check_url: Health check endpoint

        Returns:
            Service instance ID
        """
        service_id = f"{service_name}_{host}_{port}_{int(time.time())}"

        instance = ServiceInstance(
            service_id=service_id,
            service_name=service_name,
            host=host,
            port=port,
            protocol=protocol,
            version=version,
            metadata=metadata or {},
            health_check_url=health_check_url
        )

        with self.service_lock:
            # Check instance limit
            if len(self.services[service_name]) >= self.max_instances_per_service:
                # Remove oldest instance
                self.services[service_name].sort(key=lambda x: x.registered_at)
                removed = self.services[service_name].pop(0)
                logger.info(f"Removed old instance {removed.service_id} due to limit")

            self.services[service_name].append(instance)

        logger.info(f"Registered service {service_name} at {host}:{port} (ID: {service_id})")

        return service_id

    def deregister_service(self, service_id: str) -> bool:
        """
        Deregister a service instance.

        Args:
            service_id: Service instance ID

        Returns:
            Success status
        """
        with self.service_lock:
            for service_name, instances in self.services.items():
                for i, instance in enumerate(instances):
                    if instance.service_id == service_id:
                        removed = instances.pop(i)
                        logger.info(f"Deregistered service {removed.service_name} (ID: {service_id})")
                        return True

        logger.warning(f"Service {service_id} not found for deregistration")
        return False

    def discover_service(
        self,
        service_name: str,
        version: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> List[ServiceInstance]:
        """
        Discover service instances.

        Args:
            service_name: Name of service to discover
            version: Specific version requirement
            tags: Required tags in metadata

        Returns:
            List of healthy service instances
        """
        with self.service_lock:
            instances = self.services.get(service_name, [])

            # Filter healthy instances
            healthy_instances = [inst for inst in instances if inst.is_healthy()]

            # Filter by version
            if version:
                healthy_instances = [inst for inst in healthy_instances if inst.version == version]

            # Filter by tags
            if tags:
                healthy_instances = [
                    inst for inst in healthy_instances
                    if all(tag in inst.metadata.get('tags', []) for tag in tags)
                ]

            # Sort by load (simplified - would use actual load metrics)
            healthy_instances.sort(key=lambda x: x.metadata.get('load', 0))

            return healthy_instances.copy()

    def get_service_instances(self, service_name: str) -> List[ServiceInstance]:
        """
        Get all instances of a service (including unhealthy).

        Args:
            service_name: Service name

        Returns:
            List of all service instances
        """
        with self.service_lock:
            return self.services.get(service_name, []).copy()

    def update_heartbeat(self, service_id: str):
        """
        Update heartbeat for a service instance.

        Args:
            service_id: Service instance ID
        """
        with self.service_lock:
            for service_name, instances in self.services.items():
                for instance in instances:
                    if instance.service_id == service_id:
                        instance.update_heartbeat()
                        logger.debug(f"Updated heartbeat for {service_id}")
                        return

        logger.warning(f"Service {service_id} not found for heartbeat update")

    def get_all_services(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all registered services.

        Returns:
            Dictionary of service names to instance lists
        """
        with self.service_lock:
            result = {}
            for service_name, instances in self.services.items():
                result[service_name] = [inst.to_dict() for inst in instances]
            return result

    def get_service_stats(self, service_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get service statistics.

        Args:
            service_name: Specific service name, or None for all services

        Returns:
            Service statistics
        """
        with self.service_lock:
            if service_name:
                instances = self.services.get(service_name, [])
                total_instances = len(instances)
                healthy_instances = sum(1 for inst in instances if inst.is_healthy())

                return {
                    'service_name': service_name,
                    'total_instances': total_instances,
                    'healthy_instances': healthy_instances,
                    'unhealthy_instances': total_instances - healthy_instances,
                    'health_rate': healthy_instances / max(1, total_instances)
                }

            # All services stats
            stats = {}
            for svc_name, instances in self.services.items():
                stats[svc_name] = self.get_service_stats(svc_name)

            return {
                'total_services': len(self.services),
                'services': stats,
                'overall_health': self._calculate_overall_health(stats)
            }

    def _calculate_overall_health(self, service_stats: Dict[str, Any]) -> float:
        """Calculate overall system health."""
        if not service_stats:
            return 0.0

        total_instances = sum(stats['total_instances'] for stats in service_stats.values())
        healthy_instances = sum(stats['healthy_instances'] for stats in service_stats.values())

        return healthy_instances / max(1, total_instances)

    def start_cleanup_service(self):
        """Start the cleanup service for expired instances."""
        if self.running:
            return

        self.running = True
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            name='registry-cleanup',
            daemon=True
        )
        self.cleanup_thread.start()

        logger.info("Registry cleanup service started")

    def stop_cleanup_service(self):
        """Stop the cleanup service."""
        self.running = False
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=5.0)

        logger.info("Registry cleanup service stopped")

    def _cleanup_loop(self):
        """Cleanup loop for expired service instances."""
        while self.running:
            try:
                time.sleep(self.cleanup_interval)

                with self.service_lock:
                    current_time = time.time()
                    expired_instances = []

                    for service_name, instances in self.services.items():
                        for instance in instances[:]:  # Copy to avoid modification issues
                            if current_time - instance.last_heartbeat > self.heartbeat_timeout:
                                expired_instances.append((service_name, instance.service_id))
                                instances.remove(instance)

                    if expired_instances:
                        logger.info(f"Cleaned up {len(expired_instances)} expired service instances")

            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")

    def bulk_register(self, services: List[Dict[str, Any]]) -> List[str]:
        """
        Register multiple services at once.

        Args:
            services: List of service registration data

        Returns:
            List of registered service IDs
        """
        service_ids = []

        for service_data in services:
            try:
                service_id = self.register_service(
                    service_name=service_data['service_name'],
                    host=service_data['host'],
                    port=service_data['port'],
                    metadata=service_data.get('metadata'),
                    protocol=service_data.get('protocol', 'http'),
                    version=service_data.get('version', '1.0.0'),
                    health_check_url=service_data.get('health_check_url')
                )
                service_ids.append(service_id)

            except Exception as e:
                logger.error(f"Failed to register service {service_data}: {e}")

        logger.info(f"Bulk registered {len(service_ids)} services")
        return service_ids

    def get_service_metadata(self, service_name: str) -> Dict[str, Any]:
        """
        Get metadata for a service.

        Args:
            service_name: Service name

        Returns:
            Service metadata
        """
        return self.service_metadata.get(service_name, {})

    def update_service_metadata(self, service_name: str, metadata: Dict[str, Any]):
        """
        Update metadata for a service.

        Args:
            service_name: Service name
            metadata: Service metadata
        """
        self.service_metadata[service_name] = metadata
        logger.info(f"Updated metadata for service {service_name}")

    def find_services_by_capability(self, capability: str) -> List[ServiceInstance]:
        """
        Find services that have a specific capability.

        Args:
            capability: Required capability

        Returns:
            List of service instances with the capability
        """
        matching_instances = []

        with self.service_lock:
            for instances in self.services.values():
                for instance in instances:
                    if instance.is_healthy():
                        capabilities = instance.metadata.get('capabilities', [])
                        if capability in capabilities:
                            matching_instances.append(instance)

        return matching_instances

    def get_service_dependencies(self, service_name: str) -> List[str]:
        """
        Get dependencies for a service.

        Args:
            service_name: Service name

        Returns:
            List of dependent service names
        """
        metadata = self.get_service_metadata(service_name)
        return metadata.get('dependencies', [])

    def check_service_dependencies(self, service_name: str) -> Dict[str, Any]:
        """
        Check if all dependencies of a service are available.

        Args:
            service_name: Service name

        Returns:
            Dependency check results
        """
        dependencies = self.get_service_dependencies(service_name)
        results = {}

        for dep in dependencies:
            instances = self.discover_service(dep)
            results[dep] = {
                'available': len(instances) > 0,
                'instance_count': len(instances),
                'healthy_instances': len([inst for inst in instances if inst.is_healthy()])
            }

        all_available = all(result['available'] for result in results.values())

        return {
            'service_name': service_name,
            'dependencies': results,
            'all_available': all_available
        }







