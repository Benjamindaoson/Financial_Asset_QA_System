"""
Microservices Architecture for GraphRAG.

This module provides complete microservices architecture including
service discovery, communication, orchestration, monitoring, and
comprehensive service definitions for scalable deployment.
"""

from .service_registry import ServiceRegistry
from .api_gateway import APIGateway
from .service_mesh import ServiceMesh
from .orchestrator import Orchestrator
from .health_monitor import HealthMonitor
from .service_architecture import (
    GraphRAGServiceArchitecture,
    ServiceDefinition,
    APIEndpoint,
    ServiceType,
    CommunicationProtocol
)

__all__ = [
    'ServiceRegistry',
    'APIGateway',
    'ServiceMesh',
    'Orchestrator',
    'HealthMonitor',
    'GraphRAGServiceArchitecture',
    'ServiceDefinition',
    'APIEndpoint',
    'ServiceType',
    'CommunicationProtocol'
]
