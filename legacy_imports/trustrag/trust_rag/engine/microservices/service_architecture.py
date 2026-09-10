"""
Service Architecture Definition for GraphRAG.

This module defines the complete microservices architecture including service
responsibilities, communication protocols, and dependency management.
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ServiceType(Enum):
    """Types of microservices in the architecture."""
    API_GATEWAY = "api_gateway"
    SERVICE_REGISTRY = "service_registry"
    AUTH_SERVICE = "auth_service"
    QUERY_SERVICE = "query_service"
    RETRIEVAL_SERVICE = "retrieval_service"
    GENERATION_SERVICE = "generation_service"
    CHART_SERVICE = "chart_service"
    AUDIO_SERVICE = "audio_service"
    MULTIMODAL_SERVICE = "multimodal_service"
    GRAPH_SERVICE = "graph_service"
    STORAGE_SERVICE = "storage_service"
    MONITORING_SERVICE = "monitoring_service"


class CommunicationProtocol(Enum):
    """Supported communication protocols."""
    REST = "rest"
    GRPC = "grpc"
    GRAPHQL = "graphql"
    WEBSOCKET = "websocket"
    MESSAGE_QUEUE = "message_queue"


@dataclass
class ServiceDefinition:
    """Complete definition of a microservice."""
    name: str
    type: ServiceType
    description: str
    version: str = "1.0.0"
    port: int = 0
    protocol: CommunicationProtocol = CommunicationProtocol.REST
    dependencies: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    health_check_endpoint: str = "/health"
    metrics_endpoint: str = "/metrics"
    scaling_policy: Dict[str, Any] = field(default_factory=dict)
    resource_requirements: Dict[str, Any] = field(default_factory=dict)


@dataclass
class APIEndpoint:
    """API endpoint definition."""
    path: str
    method: str
    service: str
    description: str
    auth_required: bool = False
    rate_limit: Optional[int] = None
    timeout: int = 30
    parameters: Dict[str, Any] = field(default_factory=dict)
    responses: Dict[str, Any] = field(default_factory=dict)


class GraphRAGServiceArchitecture:
    """
    Complete service architecture definition for GraphRAG system.
    """

    def __init__(self):
        """Initialize service architecture."""
        self.services = {}
        self.endpoints = []
        self._define_services()
        self._define_endpoints()

    def _define_services(self):
        """Define all microservices in the architecture."""

        # API Gateway
        self.services['api-gateway'] = ServiceDefinition(
            name='api-gateway',
            type=ServiceType.API_GATEWAY,
            description='API Gateway for request routing, authentication, and load balancing',
            port=8080,
            protocol=CommunicationProtocol.REST,
            dependencies=[],
            capabilities=['routing', 'authentication', 'rate_limiting', 'load_balancing'],
            scaling_policy={
                'min_instances': 2,
                'max_instances': 10,
                'cpu_threshold': 70,
                'memory_threshold': 80
            },
            resource_requirements={
                'cpu': '500m',
                'memory': '512Mi'
            }
        )

        # Service Registry
        self.services['service-registry'] = ServiceDefinition(
            name='service-registry',
            type=ServiceType.SERVICE_REGISTRY,
            description='Service discovery and registration',
            port=8761,
            protocol=CommunicationProtocol.REST,
            dependencies=[],
            capabilities=['service_discovery', 'health_monitoring', 'load_balancing'],
            scaling_policy={
                'min_instances': 1,
                'max_instances': 3,
                'cpu_threshold': 60,
                'memory_threshold': 70
            }
        )

        # Authentication Service
        self.services['auth-service'] = ServiceDefinition(
            name='auth-service',
            type=ServiceType.AUTH_SERVICE,
            description='User authentication and authorization',
            port=8081,
            protocol=CommunicationProtocol.REST,
            dependencies=['service-registry'],
            capabilities=['user_auth', 'token_validation', 'permission_check'],
            scaling_policy={
                'min_instances': 2,
                'max_instances': 5,
                'cpu_threshold': 65,
                'memory_threshold': 75
            }
        )

        # Query Service
        self.services['query-service'] = ServiceDefinition(
            name='query-service',
            type=ServiceType.QUERY_SERVICE,
            description='Query preprocessing, analysis, and routing',
            port=8082,
            protocol=CommunicationProtocol.REST,
            dependencies=['service-registry', 'auth-service'],
            capabilities=['query_parsing', 'intent_analysis', 'query_expansion', 'validation'],
            scaling_policy={
                'min_instances': 3,
                'max_instances': 15,
                'cpu_threshold': 75,
                'memory_threshold': 85
            },
            resource_requirements={
                'cpu': '1000m',
                'memory': '1Gi'
            }
        )

        # Retrieval Service
        self.services['retrieval-service'] = ServiceDefinition(
            name='retrieval-service',
            type=ServiceType.RETRIEVAL_SERVICE,
            description='Multi-modal retrieval with vector search and graph traversal',
            port=8083,
            protocol=CommunicationProtocol.GRPC,
            dependencies=['service-registry', 'graph-service', 'storage-service'],
            capabilities=['vector_search', 'graph_traversal', 'hybrid_retrieval', 'reranking'],
            scaling_policy={
                'min_instances': 4,
                'max_instances': 20,
                'cpu_threshold': 80,
                'memory_threshold': 90
            },
            resource_requirements={
                'cpu': '2000m',
                'memory': '4Gi',
                'gpu': '1'  # For embedding computations
            }
        )

        # Generation Service
        self.services['generation-service'] = ServiceDefinition(
            name='generation-service',
            type=ServiceType.GENERATION_SERVICE,
            description='Text generation with context awareness and fact-checking',
            port=8084,
            protocol=CommunicationProtocol.GRPC,
            dependencies=['service-registry', 'retrieval-service'],
            capabilities=['text_generation', 'context_awareness', 'fact_checking', 'answer_formatting'],
            scaling_policy={
                'min_instances': 3,
                'max_instances': 12,
                'cpu_threshold': 85,
                'memory_threshold': 95
            },
            resource_requirements={
                'cpu': '2000m',
                'memory': '8Gi',
                'gpu': '1'  # For LLM inference
            }
        )

        # Chart Service
        self.services['chart-service'] = ServiceDefinition(
            name='chart-service',
            type=ServiceType.CHART_SERVICE,
            description='Chart analysis and understanding with multimodal fusion',
            port=8085,
            protocol=CommunicationProtocol.REST,
            dependencies=['service-registry'],
            capabilities=['chart_detection', 'element_extraction', 'graph_conversion', 'reasoning'],
            scaling_policy={
                'min_instances': 2,
                'max_instances': 8,
                'cpu_threshold': 70,
                'memory_threshold': 80
            },
            resource_requirements={
                'cpu': '1500m',
                'memory': '2Gi'
            }
        )

        # Audio Service
        self.services['audio-service'] = ServiceDefinition(
            name='audio-service',
            type=ServiceType.AUDIO_SERVICE,
            description='Audio transcription and processing',
            port=8086,
            protocol=CommunicationProtocol.REST,
            dependencies=['service-registry'],
            capabilities=['speech_recognition', 'audio_preprocessing', 'transcription'],
            scaling_policy={
                'min_instances': 2,
                'max_instances': 10,
                'cpu_threshold': 75,
                'memory_threshold': 85
            },
            resource_requirements={
                'cpu': '1500m',
                'memory': '2Gi'
            }
        )

        # Multimodal Service
        self.services['multimodal-service'] = ServiceDefinition(
            name='multimodal-service',
            type=ServiceType.MULTIMODAL_SERVICE,
            description='Multimodal content fusion and understanding',
            port=8087,
            protocol=CommunicationProtocol.GRPC,
            dependencies=['service-registry', 'chart-service', 'audio-service'],
            capabilities=['modality_fusion', 'cross_modal_reasoning', 'content_integration'],
            scaling_policy={
                'min_instances': 2,
                'max_instances': 6,
                'cpu_threshold': 70,
                'memory_threshold': 80
            }
        )

        # Graph Service
        self.services['graph-service'] = ServiceDefinition(
            name='graph-service',
            type=ServiceType.GRAPH_SERVICE,
            description='Knowledge graph operations and reasoning',
            port=8088,
            protocol=CommunicationProtocol.GRPC,
            dependencies=['service-registry', 'storage-service'],
            capabilities=['graph_query', 'graph_update', 'graph_reasoning', 'entity_linking'],
            scaling_policy={
                'min_instances': 3,
                'max_instances': 12,
                'cpu_threshold': 75,
                'memory_threshold': 85
            },
            resource_requirements={
                'cpu': '1500m',
                'memory': '4Gi'
            }
        )

        # Storage Service
        self.services['storage-service'] = ServiceDefinition(
            name='storage-service',
            type=ServiceType.STORAGE_SERVICE,
            description='Data storage and retrieval with vector database support',
            port=8089,
            protocol=CommunicationProtocol.GRPC,
            dependencies=['service-registry'],
            capabilities=['vector_storage', 'document_storage', 'graph_storage', 'caching'],
            scaling_policy={
                'min_instances': 3,
                'max_instances': 15,
                'cpu_threshold': 70,
                'memory_threshold': 80
            },
            resource_requirements={
                'cpu': '1000m',
                'memory': '4Gi'
            }
        )

        # Monitoring Service
        self.services['monitoring-service'] = ServiceDefinition(
            name='monitoring-service',
            type=ServiceType.MONITORING_SERVICE,
            description='System monitoring, logging, and alerting',
            port=8090,
            protocol=CommunicationProtocol.REST,
            dependencies=['service-registry'],
            capabilities=['metrics_collection', 'log_aggregation', 'alerting', 'performance_monitoring'],
            scaling_policy={
                'min_instances': 1,
                'max_instances': 3,
                'cpu_threshold': 60,
                'memory_threshold': 70
            }
        )

    def _define_endpoints(self):
        """Define API endpoints for all services."""

        # API Gateway endpoints
        self.endpoints.extend([
            APIEndpoint(
                path='/api/v1/query',
                method='POST',
                service='query-service',
                description='Main query endpoint',
                auth_required=True,
                rate_limit=100,
                timeout=60,
                parameters={
                    'query': {'type': 'string', 'required': True},
                    'context': {'type': 'object', 'required': False},
                    'options': {'type': 'object', 'required': False}
                },
                responses={
                    '200': {'description': 'Successful query response'},
                    '400': {'description': 'Invalid request'},
                    '401': {'description': 'Unauthorized'},
                    '429': {'description': 'Rate limit exceeded'}
                }
            ),
            APIEndpoint(
                path='/api/v1/health',
                method='GET',
                service='monitoring-service',
                description='System health check',
                auth_required=False,
                timeout=5
            ),
            APIEndpoint(
                path='/api/v1/upload',
                method='POST',
                service='multimodal-service',
                description='Upload multimodal content',
                auth_required=True,
                rate_limit=50,
                timeout=120,
                parameters={
                    'files': {'type': 'array', 'required': True},
                    'metadata': {'type': 'object', 'required': False}
                }
            )
        ])

        # Service-specific endpoints would be added here
        # This is a simplified version

    def get_service_definition(self, service_name: str) -> Optional[ServiceDefinition]:
        """Get service definition by name."""
        return self.services.get(service_name)

    def get_service_dependencies(self, service_name: str) -> List[str]:
        """Get dependencies for a service."""
        service = self.services.get(service_name)
        return service.dependencies if service else []

    def get_service_capabilities(self, service_name: str) -> List[str]:
        """Get capabilities for a service."""
        service = self.services.get(service_name)
        return service.capabilities if service else []

    def get_all_services(self) -> Dict[str, ServiceDefinition]:
        """Get all service definitions."""
        return self.services.copy()

    def get_endpoints_for_service(self, service_name: str) -> List[APIEndpoint]:
        """Get endpoints for a specific service."""
        return [ep for ep in self.endpoints if ep.service == service_name]

    def validate_architecture(self) -> Dict[str, Any]:
        """Validate the service architecture."""
        issues = []

        # Check for circular dependencies
        for service_name, service in self.services.items():
            if self._has_circular_dependency(service_name, service.dependencies, set()):
                issues.append(f"Circular dependency detected involving {service_name}")

        # Check for missing dependencies
        for service_name, service in self.services.items():
            for dep in service.dependencies:
                if dep not in self.services:
                    issues.append(f"Service {service_name} depends on non-existent service {dep}")

        # Check for port conflicts
        ports = {}
        for service_name, service in self.services.items():
            if service.port in ports:
                issues.append(f"Port conflict: {service.port} used by {ports[service.port]} and {service_name}")
            else:
                ports[service.port] = service_name

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'service_count': len(self.services),
            'total_endpoints': len(self.endpoints)
        }

    def _has_circular_dependency(self, service_name: str, dependencies: List[str], visited: set) -> bool:
        """Check for circular dependencies."""
        if service_name in visited:
            return True

        visited.add(service_name)

        for dep in dependencies:
            if dep in self.services:
                if self._has_circular_dependency(dep, self.services[dep].dependencies, visited.copy()):
                    return True

        return False

    def generate_deployment_config(self, target_platform: str = 'kubernetes') -> Dict[str, Any]:
        """Generate deployment configuration."""
        if target_platform == 'kubernetes':
            return self._generate_kubernetes_config()
        elif target_platform == 'docker_compose':
            return self._generate_docker_compose_config()
        else:
            raise ValueError(f"Unsupported platform: {target_platform}")

    def _generate_kubernetes_config(self) -> Dict[str, Any]:
        """Generate Kubernetes deployment configuration."""
        deployments = {}
        services = {}

        for service_name, service_def in self.services.items():
            # Generate deployment spec
            deployment = {
                'apiVersion': 'apps/v1',
                'kind': 'Deployment',
                'metadata': {
                    'name': service_name,
                    'labels': {'app': service_name}
                },
                'spec': {
                    'replicas': service_def.scaling_policy.get('min_instances', 1),
                    'selector': {'matchLabels': {'app': service_name}},
                    'template': {
                        'metadata': {'labels': {'app': service_name}},
                        'spec': {
                            'containers': [{
                                'name': service_name,
                                'image': f'graphrag/{service_name}:latest',
                                'ports': [{'containerPort': service_def.port}],
                                'resources': {
                                    'requests': service_def.resource_requirements,
                                    'limits': service_def.resource_requirements
                                },
                                'livenessProbe': {
                                    'httpGet': {
                                        'path': service_def.health_check_endpoint,
                                        'port': service_def.port
                                    },
                                    'initialDelaySeconds': 30,
                                    'periodSeconds': 10
                                },
                                'readinessProbe': {
                                    'httpGet': {
                                        'path': service_def.health_check_endpoint,
                                        'port': service_def.port
                                    },
                                    'initialDelaySeconds': 5,
                                    'periodSeconds': 5
                                }
                            }]
                        }
                    }
                }
            }

            # Add HPA if scaling policy defined
            if 'cpu_threshold' in service_def.scaling_policy:
                hpa = {
                    'apiVersion': 'autoscaling/v2',
                    'kind': 'HorizontalPodAutoscaler',
                    'metadata': {'name': f'{service_name}-hpa'},
                    'spec': {
                        'scaleTargetRef': {
                            'apiVersion': 'apps/v1',
                            'kind': 'Deployment',
                            'name': service_name
                        },
                        'minReplicas': service_def.scaling_policy['min_instances'],
                        'maxReplicas': service_def.scaling_policy['max_instances'],
                        'metrics': [{
                            'type': 'Resource',
                            'resource': {
                                'name': 'cpu',
                                'target': {
                                    'type': 'Utilization',
                                    'averageUtilization': service_def.scaling_policy['cpu_threshold']
                                }
                            }
                        }]
                    }
                }
                deployment['hpa'] = hpa

            deployments[service_name] = deployment

            # Generate service spec
            k8s_service = {
                'apiVersion': 'v1',
                'kind': 'Service',
                'metadata': {
                    'name': service_name,
                    'labels': {'app': service_name}
                },
                'spec': {
                    'selector': {'app': service_name},
                    'ports': [{
                        'port': service_def.port,
                        'targetPort': service_def.port,
                        'protocol': 'TCP'
                    }]
                }
            }
            services[service_name] = k8s_service

        return {
            'deployments': deployments,
            'services': services,
            'configmaps': {},
            'secrets': {}
        }

    def _generate_docker_compose_config(self) -> Dict[str, Any]:
        """Generate Docker Compose configuration."""
        services = {}

        for service_name, service_def in self.services.items():
            compose_service = {
                'image': f'graphrag/{service_name}:latest',
                'ports': [f"{service_def.port}:{service_def.port}"],
                'environment': [
                    f'SERVICE_NAME={service_name}',
                    f'SERVICE_PORT={service_def.port}',
                    'SERVICE_REGISTRY_URL=http://service-registry:8761'
                ],
                'depends_on': service_def.dependencies,
                'healthcheck': {
                    'test': ['CMD', 'curl', '-f', f'http://localhost:{service_def.port}{service_def.health_check_endpoint}'],
                    'interval': '30s',
                    'timeout': '10s',
                    'retries': 3
                },
                'deploy': {
                    'replicas': service_def.scaling_policy.get('min_instances', 1),
                    'resources': {
                        'limits': service_def.resource_requirements,
                        'reservations': service_def.resource_requirements
                    }
                }
            }

            # Add restart policy
            compose_service['restart'] = 'unless-stopped'

            services[service_name] = compose_service

        return {
            'version': '3.8',
            'services': services,
            'networks': {
                'graphrag-network': {
                    'driver': 'bridge'
                }
            }
        }

    def get_communication_matrix(self) -> Dict[str, List[str]]:
        """Get service communication matrix."""
        matrix = {}

        for service_name, service in self.services.items():
            communicates_with = set()

            # Direct dependencies
            communicates_with.update(service.dependencies)

            # Services that depend on this service
            for other_name, other_service in self.services.items():
                if service_name in other_service.dependencies:
                    communicates_with.add(other_name)

            matrix[service_name] = sorted(list(communicates_with))

        return matrix

    def analyze_scalability(self) -> Dict[str, Any]:
        """Analyze system scalability characteristics."""
        total_cpu = 0
        total_memory = 0
        max_instances = 0

        for service in self.services.values():
            # Calculate resource requirements
            cpu_req = service.resource_requirements.get('cpu', '500m')
            mem_req = service.resource_requirements.get('memory', '512Mi')

            # Parse CPU (simplified)
            if cpu_req.endswith('m'):
                cpu_cores = int(cpu_req[:-1]) / 1000
            else:
                cpu_cores = float(cpu_req)

            # Parse memory (simplified)
            if mem_req.endswith('Gi'):
                mem_gb = float(mem_req[:-2])
            elif mem_req.endswith('Mi'):
                mem_gb = float(mem_req[:-2]) / 1024
            else:
                mem_gb = 0.5  # default

            max_instances_service = service.scaling_policy.get('max_instances', 1)

            total_cpu += cpu_cores * max_instances_service
            total_memory += mem_gb * max_instances_service
            max_instances += max_instances_service

        return {
            'total_services': len(self.services),
            'max_total_instances': max_instances,
            'peak_cpu_cores': total_cpu,
            'peak_memory_gb': total_memory,
            'scalability_score': self._calculate_scalability_score(total_cpu, total_memory, max_instances)
        }

    def _calculate_scalability_score(self, total_cpu: float, total_memory: float, max_instances: int) -> float:
        """Calculate scalability score (0-1, higher is better)."""
        # Simplified scoring based on resource efficiency
        cpu_efficiency = min(1.0, 32 / total_cpu)  # Assuming 32 core cluster
        memory_efficiency = min(1.0, 128 / total_memory)  # Assuming 128GB cluster
        instance_efficiency = min(1.0, 50 / max_instances)  # Assuming 50 instance limit

        return (cpu_efficiency + memory_efficiency + instance_efficiency) / 3

    def export_architecture(self, format: str = 'json') -> str:
        """Export architecture definition."""
        data = {
            'services': {name: vars(service) for name, service in self.services.items()},
            'endpoints': [vars(ep) for ep in self.endpoints],
            'communication_matrix': self.get_communication_matrix(),
            'scalability_analysis': self.analyze_scalability(),
            'validation': self.validate_architecture()
        }

        if format == 'json':
            import json
            return json.dumps(data, indent=2, default=str)
        else:
            raise ValueError(f"Unsupported export format: {format}")







