"""
Service Orchestrator for GraphRAG Microservices.

This module provides service orchestration capabilities for coordinating
complex workflows across multiple microservices.
"""

import logging
from typing import Dict, List, Any, Optional, Callable, Union
import time
import asyncio
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """Workflow execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowStep:
    """Represents a step in a workflow."""
    step_id: str
    service_name: str
    operation: str
    input_data: Dict[str, Any]
    dependencies: List[str] = None  # Step IDs this step depends on
    timeout: int = 30
    retries: int = 3


@dataclass
class Workflow:
    """Represents a complete workflow."""
    workflow_id: str
    name: str
    steps: List[WorkflowStep]
    status: WorkflowStatus = WorkflowStatus.PENDING
    created_at: float = None
    started_at: float = None
    completed_at: float = None
    results: Dict[str, Any] = None
    error: str = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.results is None:
            self.results = {}


class ServiceOrchestrator:
    """
    Orchestrator for complex service workflows with dependency management.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize service orchestrator.

        Args:
            config: Orchestrator configuration
        """
        self.config = config or {}

        # Service registry integration
        self.service_registry = None

        # Workflow storage
        self.workflows: Dict[str, Workflow] = {}
        self.active_workflows: Dict[str, asyncio.Task] = {}
        self.workflow_lock = asyncio.Lock()

        # Predefined workflows
        self.workflow_templates: Dict[str, Dict[str, Any]] = {}

        # Performance monitoring
        self.execution_stats = defaultdict(list)

        logger.info("Service orchestrator initialized")

    def set_service_registry(self, registry):
        """Set service registry for service discovery."""
        self.service_registry = registry
        logger.info("Service registry connected to orchestrator")

    def define_workflow_template(self, template_name: str, template: Dict[str, Any]):
        """
        Define a workflow template.

        Args:
            template_name: Name of the template
            template: Workflow template definition
        """
        self.workflow_templates[template_name] = template
        logger.info(f"Defined workflow template: {template_name}")

    def execute_workflow_template(
        self,
        template_name: str,
        input_data: Dict[str, Any],
        workflow_id: Optional[str] = None
    ) -> str:
        """
        Execute a workflow from template.

        Args:
            template_name: Template name
            input_data: Input data for the workflow
            workflow_id: Optional custom workflow ID

        Returns:
            Workflow ID
        """
        if template_name not in self.workflow_templates:
            raise ValueError(f"Workflow template {template_name} not found")

        template = self.workflow_templates[template_name]

        # Create workflow steps from template
        steps = []
        for step_data in template['steps']:
            step = WorkflowStep(
                step_id=step_data['step_id'],
                service_name=step_data['service'],
                operation=step_data['operation'],
                input_data=input_data,
                dependencies=step_data.get('dependencies', []),
                timeout=step_data.get('timeout', 30),
                retries=step_data.get('retries', 3)
            )
            steps.append(step)

        workflow_id = workflow_id or f"workflow_{int(time.time())}_{template_name}"

        workflow = Workflow(
            workflow_id=workflow_id,
            name=template_name,
            steps=steps
        )

        return self._execute_workflow(workflow)

    def create_workflow(
        self,
        name: str,
        steps: List[Dict[str, Any]],
        workflow_id: Optional[str] = None
    ) -> str:
        """
        Create and execute a custom workflow.

        Args:
            name: Workflow name
            steps: List of step definitions
            workflow_id: Optional custom workflow ID

        Returns:
            Workflow ID
        """
        workflow_steps = []
        for step_data in steps:
            step = WorkflowStep(
                step_id=step_data['step_id'],
                service_name=step_data['service'],
                operation=step_data['operation'],
                input_data=step_data.get('input_data', {}),
                dependencies=step_data.get('dependencies', []),
                timeout=step_data.get('timeout', 30),
                retries=step_data.get('retries', 3)
            )
            workflow_steps.append(step)

        workflow_id = workflow_id or f"workflow_{int(time.time())}_{name}"

        workflow = Workflow(
            workflow_id=workflow_id,
            name=name,
            steps=workflow_steps
        )

        return self._execute_workflow(workflow)

    def _execute_workflow(self, workflow: Workflow) -> str:
        """Execute a workflow asynchronously."""
        async def run_workflow():
            try:
                workflow.status = WorkflowStatus.RUNNING
                workflow.started_at = time.time()

                async with self.workflow_lock:
                    self.workflows[workflow.workflow_id] = workflow

                # Execute workflow steps
                results = await self._execute_workflow_steps(workflow)

                workflow.status = WorkflowStatus.COMPLETED
                workflow.completed_at = time.time()
                workflow.results = results

                logger.info(f"Workflow {workflow.workflow_id} completed successfully")

            except Exception as e:
                workflow.status = WorkflowStatus.FAILED
                workflow.completed_at = time.time()
                workflow.error = str(e)

                logger.error(f"Workflow {workflow.workflow_id} failed: {e}")

        # Start workflow execution
        task = asyncio.create_task(run_workflow())
        self.active_workflows[workflow.workflow_id] = task

        return workflow.workflow_id

    async def _execute_workflow_steps(self, workflow: Workflow) -> Dict[str, Any]:
        """Execute workflow steps with dependency resolution."""
        results = {}
        completed_steps = set()
        pending_steps = {step.step_id: step for step in workflow.steps}

        while pending_steps:
            # Find steps that can be executed (all dependencies met)
            executable_steps = []
            for step_id, step in pending_steps.items():
                if all(dep in completed_steps for dep in step.dependencies):
                    executable_steps.append(step)

            if not executable_steps:
                raise ValueError("Circular dependency or missing dependency detected")

            # Execute steps in parallel
            tasks = []
            for step in executable_steps:
                task = asyncio.create_task(self._execute_step(step, results))
                tasks.append((step.step_id, task))

            # Wait for completion
            for step_id, task in tasks:
                try:
                    step_result = await task
                    results[step_id] = step_result
                    completed_steps.add(step_id)
                    del pending_steps[step_id]

                    logger.debug(f"Step {step_id} completed")

                except Exception as e:
                    logger.error(f"Step {step_id} failed: {e}")
                    raise

        return results

    async def _execute_step(self, step: WorkflowStep, previous_results: Dict[str, Any]) -> Any:
        """Execute a single workflow step."""
        if not self.service_registry:
            raise ValueError("Service registry not available")

        # Discover service
        instances = self.service_registry.discover_service(step.service_name)
        if not instances:
            raise ValueError(f"Service {step.service_name} not available")

        # Prepare input data
        input_data = step.input_data.copy()

        # Include results from dependency steps
        for dep in step.dependencies:
            if dep in previous_results:
                input_data[f"{dep}_result"] = previous_results[dep]

        # Execute with retries
        last_error = None
        for attempt in range(step.retries + 1):
            try:
                result = await self._call_service(instances[0], step.operation, input_data, step.timeout)
                return result

            except Exception as e:
                last_error = e
                if attempt < step.retries:
                    logger.warning(f"Step {step.step_id} attempt {attempt + 1} failed, retrying: {e}")
                    await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
                else:
                    logger.error(f"Step {step.step_id} failed after {step.retries + 1} attempts: {e}")

        raise last_error

    async def _call_service(self, instance, operation: str, input_data: Dict[str, Any], timeout: int) -> Any:
        """Call a service operation."""
        import aiohttp

        url = f"{instance.get_url()}/{operation}"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=input_data,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    raise Exception(f"Service call failed: {response.status} - {error_text}")

    def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get workflow execution status.

        Args:
            workflow_id: Workflow ID

        Returns:
            Workflow status information
        """
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return {'status': 'not_found'}

        status = {
            'workflow_id': workflow.workflow_id,
            'name': workflow.name,
            'status': workflow.status.value,
            'created_at': workflow.created_at,
            'started_at': workflow.started_at,
            'completed_at': workflow.completed_at,
            'total_steps': len(workflow.steps),
            'results': workflow.results,
            'error': workflow.error
        }

        return status

    def cancel_workflow(self, workflow_id: str) -> bool:
        """
        Cancel a running workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Success status
        """
        if workflow_id not in self.active_workflows:
            return False

        task = self.active_workflows[workflow_id]
        task.cancel()

        # Update workflow status
        workflow = self.workflows.get(workflow_id)
        if workflow:
            workflow.status = WorkflowStatus.CANCELLED
            workflow.completed_at = time.time()

        del self.active_workflows[workflow_id]

        logger.info(f"Cancelled workflow {workflow_id}")
        return True

    def get_workflow_templates(self) -> Dict[str, Dict[str, Any]]:
        """Get all defined workflow templates."""
        return self.workflow_templates.copy()

    def get_execution_stats(self) -> Dict[str, Any]:
        """Get workflow execution statistics."""
        total_workflows = len(self.workflows)
        completed_workflows = sum(1 for w in self.workflows.values() if w.status == WorkflowStatus.COMPLETED)
        failed_workflows = sum(1 for w in self.workflows.values() if w.status == WorkflowStatus.FAILED)

        success_rate = completed_workflows / max(1, total_workflows)

        # Calculate average execution time
        execution_times = []
        for workflow in self.workflows.values():
            if workflow.completed_at and workflow.started_at:
                execution_times.append(workflow.completed_at - workflow.started_at)

        avg_execution_time = sum(execution_times) / max(1, len(execution_times)) if execution_times else 0

        return {
            'total_workflows': total_workflows,
            'completed_workflows': completed_workflows,
            'failed_workflows': failed_workflows,
            'success_rate': success_rate,
            'avg_execution_time': avg_execution_time,
            'active_workflows': len(self.active_workflows)
        }

    def cleanup_completed_workflows(self, max_age: int = 3600):
        """
        Clean up old completed workflows.

        Args:
            max_age: Maximum age in seconds for completed workflows
        """
        current_time = time.time()
        to_remove = []

        for workflow_id, workflow in self.workflows.items():
            if (workflow.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED] and
                workflow.completed_at and
                current_time - workflow.completed_at > max_age):
                to_remove.append(workflow_id)

        for workflow_id in to_remove:
            del self.workflows[workflow_id]

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old workflows")

    def create_rag_workflow_template(self):
        """Create a standard RAG (Retrieval-Augmented Generation) workflow template."""
        template = {
            'description': 'Standard RAG workflow for question answering',
            'steps': [
                {
                    'step_id': 'preprocess_query',
                    'service': 'query_processor',
                    'operation': 'preprocess',
                    'dependencies': [],
                    'timeout': 10
                },
                {
                    'step_id': 'retrieve_documents',
                    'service': 'retrieval_service',
                    'operation': 'retrieve',
                    'dependencies': ['preprocess_query'],
                    'timeout': 30
                },
                {
                    'step_id': 'rank_documents',
                    'service': 'ranking_service',
                    'operation': 'rank',
                    'dependencies': ['retrieve_documents'],
                    'timeout': 15
                },
                {
                    'step_id': 'generate_answer',
                    'service': 'generation_service',
                    'operation': 'generate',
                    'dependencies': ['rank_documents'],
                    'timeout': 45
                },
                {
                    'step_id': 'postprocess_answer',
                    'service': 'postprocessor',
                    'operation': 'postprocess',
                    'dependencies': ['generate_answer'],
                    'timeout': 10
                }
            ]
        }

        self.define_workflow_template('rag_workflow', template)

    def create_multimodal_workflow_template(self):
        """Create a multimodal processing workflow template."""
        template = {
            'description': 'Multimodal content processing workflow',
            'steps': [
                {
                    'step_id': 'detect_modality',
                    'service': 'modality_detector',
                    'operation': 'detect',
                    'dependencies': [],
                    'timeout': 10
                },
                {
                    'step_id': 'process_text',
                    'service': 'text_processor',
                    'operation': 'process',
                    'dependencies': ['detect_modality'],
                    'timeout': 20
                },
                {
                    'step_id': 'process_image',
                    'service': 'image_processor',
                    'operation': 'process',
                    'dependencies': ['detect_modality'],
                    'timeout': 30
                },
                {
                    'step_id': 'process_audio',
                    'service': 'audio_processor',
                    'operation': 'process',
                    'dependencies': ['detect_modality'],
                    'timeout': 45
                },
                {
                    'step_id': 'fuse_modalities',
                    'service': 'fusion_service',
                    'operation': 'fuse',
                    'dependencies': ['process_text', 'process_image', 'process_audio'],
                    'timeout': 25
                },
                {
                    'step_id': 'generate_response',
                    'service': 'generation_service',
                    'operation': 'generate',
                    'dependencies': ['fuse_modalities'],
                    'timeout': 40
                }
            ]
        }

        self.define_workflow_template('multimodal_workflow', template)







