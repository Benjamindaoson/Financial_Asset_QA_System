"""
Health Monitor for GraphRAG Microservices.

This module provides comprehensive health monitoring and alerting for microservices,
including performance metrics, dependency checks, and automatic recovery.
"""

import logging
from typing import Dict, List, Any, Optional, Callable, Union
import time
import threading
import psutil
import requests
from datetime import datetime, timedelta
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


class HealthMonitor:
    """
    Comprehensive health monitoring system for microservices.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize health monitor.

        Args:
            config: Monitoring configuration
        """
        self.config = config or {}

        # Monitoring settings
        self.check_interval = self.config.get('check_interval', 30.0)  # seconds
        self.health_timeout = self.config.get('health_timeout', 10.0)  # seconds
        self.max_history_size = self.config.get('max_history_size', 1000)

        # Service registry integration
        self.service_registry = None

        # Health check endpoints
        self.health_endpoints = {}

        # Monitoring data
        self.health_history = defaultdict(list)
        self.performance_metrics = defaultdict(list)
        self.alerts = []

        # Alert thresholds
        self.alert_thresholds = {
            'response_time': self.config.get('response_time_threshold', 5.0),  # seconds
            'error_rate': self.config.get('error_rate_threshold', 0.1),  # 10%
            'cpu_usage': self.config.get('cpu_threshold', 0.8),  # 80%
            'memory_usage': self.config.get('memory_threshold', 0.8),  # 80%
            'unhealthy_duration': self.config.get('unhealthy_duration', 300.0)  # 5 minutes
        }

        # Alert callbacks
        self.alert_callbacks: List[Callable] = []

        # Monitoring thread
        self.monitoring_thread = None
        self.monitoring_active = False

        # Recovery actions
        self.recovery_actions = self._init_recovery_actions()

        logger.info("Health monitor initialized")

    def set_service_registry(self, registry):
        """Set service registry for service discovery."""
        self.service_registry = registry
        logger.info("Service registry connected to health monitor")

    def add_health_endpoint(self, service_name: str, endpoint: str, method: str = 'GET'):
        """
        Add a custom health check endpoint for a service.

        Args:
            service_name: Name of the service
            endpoint: Health check endpoint URL
            method: HTTP method for health check
        """
        self.health_endpoints[service_name] = {
            'endpoint': endpoint,
            'method': method,
            'last_check': None,
            'status': 'unknown'
        }
        logger.info(f"Added health endpoint for {service_name}: {endpoint}")

    def start_monitoring(self):
        """Start the health monitoring system."""
        if self.monitoring_active:
            return

        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            name='health-monitor',
            daemon=True
        )
        self.monitoring_thread.start()

        logger.info("Health monitoring started")

    def stop_monitoring(self):
        """Stop the health monitoring system."""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5.0)

        logger.info("Health monitoring stopped")

    def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.monitoring_active:
            try:
                # Perform health checks
                self._perform_health_checks()

                # Analyze health data
                self._analyze_health_data()

                # Check for alerts
                self._check_alerts()

                # Perform maintenance
                self._maintenance_tasks()

                # Wait for next check
                time.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                time.sleep(self.check_interval)

    def _perform_health_checks(self):
        """Perform health checks on all services."""
        if not self.service_registry:
            return

        # Get all services from registry
        all_services = self.service_registry.get_all_services()

        for service_name, instances in all_services.items():
            for instance_data in instances:
                self._check_service_instance(service_name, instance_data)

    def _check_service_instance(self, service_name: str, instance_data: Dict[str, Any]):
        """Check health of a specific service instance."""
        instance_id = instance_data.get('service_id', 'unknown')
        instance_url = instance_data.get('protocol', 'http') + '://' + \
                      instance_data.get('host', 'localhost') + ':' + \
                      str(instance_data.get('port', 8080))

        check_start = time.time()

        try:
            # Use custom health endpoint if available
            if service_name in self.health_endpoints:
                endpoint_config = self.health_endpoints[service_name]
                check_url = endpoint_config['endpoint']
                method = endpoint_config['method']
            else:
                # Default health check
                check_url = f"{instance_url}/health"
                method = 'GET'

            # Perform health check
            response = requests.request(
                method=method,
                url=check_url,
                timeout=self.health_timeout,
                headers={'User-Agent': 'GraphRAG-HealthMonitor/1.0'}
            )

            response_time = time.time() - check_start
            is_healthy = response.status_code == 200

            # Parse health response
            health_data = {}
            if response.headers.get('content-type', '').startswith('application/json'):
                try:
                    health_data = response.json()
                except:
                    pass

            # Record health status
            health_record = {
                'timestamp': time.time(),
                'service_name': service_name,
                'instance_id': instance_id,
                'url': instance_url,
                'status_code': response.status_code,
                'response_time': response_time,
                'healthy': is_healthy,
                'health_data': health_data,
                'error': None
            }

        except requests.exceptions.RequestException as e:
            response_time = time.time() - check_start
            health_record = {
                'timestamp': time.time(),
                'service_name': service_name,
                'instance_id': instance_id,
                'url': instance_url,
                'status_code': None,
                'response_time': response_time,
                'healthy': False,
                'health_data': {},
                'error': str(e)
            }

        except Exception as e:
            response_time = time.time() - check_start
            health_record = {
                'timestamp': time.time(),
                'service_name': service_name,
                'instance_id': instance_id,
                'url': instance_url,
                'status_code': None,
                'response_time': response_time,
                'healthy': False,
                'health_data': {},
                'error': str(e)
            }

        # Store health record
        key = f"{service_name}:{instance_id}"
        self.health_history[key].append(health_record)

        # Maintain history size
        if len(self.health_history[key]) > self.max_history_size:
            self.health_history[key] = self.health_history[key][-self.max_history_size:]

        # Update endpoint status
        if service_name in self.health_endpoints:
            self.health_endpoints[service_name]['last_check'] = time.time()
            self.health_endpoints[service_name]['status'] = 'healthy' if health_record['healthy'] else 'unhealthy'

    def _analyze_health_data(self):
        """Analyze health data and compute metrics."""
        current_time = time.time()
        analysis_window = 300.0  # 5 minutes

        for key, history in self.health_history.items():
            if not history:
                continue

            # Get recent health checks
            recent_checks = [
                record for record in history
                if current_time - record['timestamp'] < analysis_window
            ]

            if not recent_checks:
                continue

            # Calculate metrics
            total_checks = len(recent_checks)
            healthy_checks = sum(1 for record in recent_checks if record['healthy'])
            error_rate = (total_checks - healthy_checks) / total_checks

            response_times = [record['response_time'] for record in recent_checks if record['response_time']]
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0

            # Store metrics
            metrics_record = {
                'timestamp': current_time,
                'service_key': key,
                'total_checks': total_checks,
                'healthy_checks': healthy_checks,
                'error_rate': error_rate,
                'avg_response_time': avg_response_time,
                'uptime_percentage': healthy_checks / total_checks
            }

            self.performance_metrics[key].append(metrics_record)

            # Maintain metrics history
            if len(self.performance_metrics[key]) > self.max_history_size // 10:  # Keep less metrics history
                self.performance_metrics[key] = self.performance_metrics[key][-(self.max_history_size // 10):]

    def _check_alerts(self):
        """Check for health alerts based on thresholds."""
        current_time = time.time()

        for key, metrics_history in self.performance_metrics.items():
            if not metrics_history:
                continue

            latest_metrics = metrics_history[-1]

            # Check response time alert
            if latest_metrics['avg_response_time'] > self.alert_thresholds['response_time']:
                self._trigger_alert('high_response_time', key, latest_metrics)

            # Check error rate alert
            if latest_metrics['error_rate'] > self.alert_thresholds['error_rate']:
                self._trigger_alert('high_error_rate', key, latest_metrics)

            # Check system resource alerts
            self._check_system_resource_alerts(key)

            # Check prolonged unhealthy status
            self._check_prolonged_unhealthy(key, current_time)

    def _check_system_resource_alerts(self, service_key: str):
        """Check system resource usage alerts."""
        try:
            # CPU usage
            cpu_usage = psutil.cpu_percent() / 100.0
            if cpu_usage > self.alert_thresholds['cpu_usage']:
                self._trigger_alert('high_cpu_usage', service_key, {'cpu_usage': cpu_usage})

            # Memory usage
            memory_usage = psutil.virtual_memory().percent / 100.0
            if memory_usage > self.alert_thresholds['memory_usage']:
                self._trigger_alert('high_memory_usage', service_key, {'memory_usage': memory_usage})

        except Exception as e:
            logger.warning(f"Resource check failed: {e}")

    def _check_prolonged_unhealthy(self, service_key: str, current_time: float):
        """Check for services that have been unhealthy for too long."""
        health_history = self.health_history.get(service_key, [])

        if not health_history:
            return

        # Find consecutive unhealthy checks
        unhealthy_duration = 0
        check_interval = self.check_interval

        for record in reversed(health_history):
            if record['healthy']:
                break
            unhealthy_duration += check_interval

        if unhealthy_duration > self.alert_thresholds['unhealthy_duration']:
            self._trigger_alert('prolonged_unhealthy', service_key, {
                'unhealthy_duration': unhealthy_duration,
                'threshold': self.alert_thresholds['unhealthy_duration']
            })

    def _trigger_alert(self, alert_type: str, service_key: str, data: Dict[str, Any]):
        """Trigger a health alert."""
        alert = {
            'alert_id': f"{alert_type}_{service_key}_{int(time.time())}",
            'alert_type': alert_type,
            'service_key': service_key,
            'timestamp': time.time(),
            'data': data,
            'severity': self._determine_alert_severity(alert_type, data),
            'message': self._generate_alert_message(alert_type, service_key, data)
        }

        self.alerts.append(alert)

        # Keep only recent alerts
        max_alerts = 1000
        if len(self.alerts) > max_alerts:
            self.alerts = self.alerts[-max_alerts:]

        # Call alert callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")

        logger.warning(f"Alert triggered: {alert['message']}")

    def _determine_alert_severity(self, alert_type: str, data: Dict[str, Any]) -> str:
        """Determine alert severity."""
        if alert_type in ['prolonged_unhealthy', 'service_down']:
            return 'critical'
        elif alert_type in ['high_error_rate', 'high_cpu_usage', 'high_memory_usage']:
            return 'warning'
        elif alert_type == 'high_response_time':
            response_time = data.get('avg_response_time', 0)
            if response_time > self.alert_thresholds['response_time'] * 2:
                return 'critical'
            else:
                return 'warning'
        else:
            return 'info'

    def _generate_alert_message(self, alert_type: str, service_key: str, data: Dict[str, Any]) -> str:
        """Generate human-readable alert message."""
        service_name = service_key.split(':')[0]

        messages = {
            'high_response_time': f"High response time for {service_name}: {data.get('avg_response_time', 0):.2f}s",
            'high_error_rate': f"High error rate for {service_name}: {data.get('error_rate', 0)*100:.1f}%",
            'high_cpu_usage': f"High CPU usage: {data.get('cpu_usage', 0)*100:.1f}%",
            'high_memory_usage': f"High memory usage: {data.get('memory_usage', 0)*100:.1f}%",
            'prolonged_unhealthy': f"Service {service_name} has been unhealthy for {data.get('unhealthy_duration', 0):.0f} seconds"
        }

        return messages.get(alert_type, f"Alert: {alert_type} for {service_key}")

    def add_alert_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Add an alert callback function."""
        self.alert_callbacks.append(callback)
        logger.info("Alert callback added")

    def _init_recovery_actions(self) -> Dict[str, Callable]:
        """Initialize recovery actions for different alert types."""
        return {
            'restart_service': self._restart_service,
            'scale_service': self._scale_service,
            'failover': self._failover_service,
            'notify_admin': self._notify_admin
        }

    def _restart_service(self, service_key: str):
        """Attempt to restart a service."""
        logger.info(f"Attempting to restart service: {service_key}")
        # Implementation would depend on deployment system (Kubernetes, Docker, etc.)

    def _scale_service(self, service_key: str):
        """Scale up a service."""
        logger.info(f"Attempting to scale service: {service_key}")
        # Implementation would depend on orchestration system

    def _failover_service(self, service_key: str):
        """Perform failover for a service."""
        logger.info(f"Performing failover for service: {service_key}")
        # Implementation would depend on load balancer and service mesh

    def _notify_admin(self, alert: Dict[str, Any]):
        """Notify administrators of critical alerts."""
        logger.critical(f"Admin notification: {alert['message']}")
        # Implementation would send emails, Slack messages, etc.

    def get_health_status(self, service_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get current health status.

        Args:
            service_name: Specific service name, or None for all services

        Returns:
            Health status information
        """
        if service_name:
            # Specific service status
            service_keys = [key for key in self.health_history.keys() if key.startswith(f"{service_name}:")]

            if not service_keys:
                return {'status': 'not_found', 'service_name': service_name}

            service_status = {
                'service_name': service_name,
                'instances': {}
            }

            for key in service_keys:
                instance_name = key.split(':', 1)[1]
                latest_health = self.health_history[key][-1] if self.health_history[key] else None

                if latest_health:
                    service_status['instances'][instance_name] = {
                        'healthy': latest_health['healthy'],
                        'response_time': latest_health['response_time'],
                        'last_check': latest_health['timestamp'],
                        'status_code': latest_health['status_code']
                    }

            return service_status

        else:
            # Overall system status
            total_instances = len(self.health_history)
            healthy_instances = sum(
                1 for key in self.health_history.keys()
                if self.health_history[key] and self.health_history[key][-1]['healthy']
            )

            return {
                'total_instances': total_instances,
                'healthy_instances': healthy_instances,
                'unhealthy_instances': total_instances - healthy_instances,
                'overall_health': healthy_instances / total_instances if total_instances > 0 else 0,
                'active_alerts': len([a for a in self.alerts if time.time() - a['timestamp'] < 3600]),  # Last hour
                'last_check': time.time()
            }

    def get_performance_metrics(self, service_key: Optional[str] = None, time_window: float = 3600.0) -> Dict[str, Any]:
        """
        Get performance metrics.

        Args:
            service_key: Specific service key, or None for all services
            time_window: Time window in seconds for metrics

        Returns:
            Performance metrics
        """
        current_time = time.time()
        window_start = current_time - time_window

        if service_key:
            # Specific service metrics
            metrics_history = self.performance_metrics.get(service_key, [])
            recent_metrics = [m for m in metrics_history if m['timestamp'] > window_start]

            if not recent_metrics:
                return {'status': 'no_data', 'service_key': service_key}

            # Aggregate metrics
            avg_response_time = sum(m['avg_response_time'] for m in recent_metrics) / len(recent_metrics)
            avg_error_rate = sum(m['error_rate'] for m in recent_metrics) / len(recent_metrics)
            avg_uptime = sum(m['uptime_percentage'] for m in recent_metrics) / len(recent_metrics)

            return {
                'service_key': service_key,
                'time_window': time_window,
                'avg_response_time': avg_response_time,
                'avg_error_rate': avg_error_rate,
                'avg_uptime_percentage': avg_uptime,
                'data_points': len(recent_metrics)
            }

        else:
            # All services metrics
            all_metrics = {}

            for key, metrics_history in self.performance_metrics.items():
                recent_metrics = [m for m in metrics_history if m['timestamp'] > window_start]
                if recent_metrics:
                    all_metrics[key] = {
                        'avg_response_time': sum(m['avg_response_time'] for m in recent_metrics) / len(recent_metrics),
                        'avg_error_rate': sum(m['error_rate'] for m in recent_metrics) / len(recent_metrics),
                        'avg_uptime_percentage': sum(m['uptime_percentage'] for m in recent_metrics) / len(recent_metrics),
                        'data_points': len(recent_metrics)
                    }

            return {
                'services': all_metrics,
                'time_window': time_window,
                'total_services': len(all_metrics)
            }

    def get_alerts(self, time_window: float = 3600.0, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get recent alerts.

        Args:
            time_window: Time window in seconds
            severity: Filter by severity level

        Returns:
            List of recent alerts
        """
        current_time = time.time()
        window_start = current_time - time_window

        alerts = [
            alert for alert in self.alerts
            if alert['timestamp'] > window_start
        ]

        if severity:
            alerts = [alert for alert in alerts if alert['severity'] == severity]

        return sorted(alerts, key=lambda x: x['timestamp'], reverse=True)

    def export_health_data(self, filepath: str):
        """
        Export health monitoring data to file.

        Args:
            filepath: Export file path
        """
        export_data = {
            'timestamp': time.time(),
            'health_history': dict(self.health_history),
            'performance_metrics': dict(self.performance_metrics),
            'alerts': self.alerts,
            'configuration': self.config
        }

        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)

        logger.info(f"Health data exported to {filepath}")

    def clear_old_data(self, max_age: float = 86400.0):
        """
        Clear old monitoring data.

        Args:
            max_age: Maximum age in seconds for data to keep
        """
        current_time = time.time()
        cutoff_time = current_time - max_age

        # Clear old health history
        for key in list(self.health_history.keys()):
            self.health_history[key] = [
                record for record in self.health_history[key]
                if record['timestamp'] > cutoff_time
            ]

        # Clear old performance metrics
        for key in list(self.performance_metrics.keys()):
            self.performance_metrics[key] = [
                record for record in self.performance_metrics[key]
                if record['timestamp'] > cutoff_time
            ]

        # Clear old alerts
        self.alerts = [
            alert for alert in self.alerts
            if alert['timestamp'] > cutoff_time
        ]

        logger.info(f"Cleared monitoring data older than {max_age} seconds")

    def _maintenance_tasks(self):
        """Perform periodic maintenance tasks."""
        # Clear old data (keep last 24 hours)
        self.clear_old_data(86400.0)

        # Check for zombie services
        self._cleanup_zombie_services()

    def _cleanup_zombie_services(self):
        """Clean up services that haven't been seen recently."""
        current_time = time.time()
        zombie_threshold = 600.0  # 10 minutes

        zombie_keys = []
        for key, history in self.health_history.items():
            if history and current_time - history[-1]['timestamp'] > zombie_threshold:
                zombie_keys.append(key)

        for key in zombie_keys:
            del self.health_history[key]
            if key in self.performance_metrics:
                del self.performance_metrics[key]

        if zombie_keys:
            logger.info(f"Cleaned up {len(zombie_keys)} zombie services")
