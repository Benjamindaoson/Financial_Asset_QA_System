"""
Inference Optimizer for GraphRAG.

This module provides comprehensive inference optimization including
model compilation, caching, and hardware acceleration.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import torch
import torch.nn as nn
from functools import lru_cache
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import psutil
import GPUtil

logger = logging.getLogger(__name__)


class InferenceOptimizer:
    """
    Comprehensive inference optimization for GraphRAG models.
    """

    def __init__(self, optimization_config: Optional[Dict[str, Any]] = None):
        """
        Initialize inference optimizer.

        Args:
            optimization_config: Optimization configuration
        """
        self.optimization_config = optimization_config or {
            'enable_caching': True,
            'cache_size': 1000,
            'enable_jit': True,
            'enable_fp16': True,
            'max_batch_size': 32,
            'num_threads': 4,
            'memory_limit_gb': 8,
            'gpu_memory_limit_gb': 4
        }

        # Initialize caches
        self.result_cache = {}
        self.model_cache = {}

        # Thread pool for concurrent inference
        self.executor = ThreadPoolExecutor(
            max_workers=self.optimization_config['num_threads']
        )

        # Performance monitoring
        self.performance_stats = {
            'inference_count': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'avg_inference_time': 0.0,
            'total_inference_time': 0.0
        }

        # Hardware monitoring
        self.hardware_monitor = HardwareMonitor()

        logger.info("Inference optimizer initialized")

    def optimize_model(self, model: nn.Module, model_name: str = 'default') -> nn.Module:
        """
        Apply comprehensive optimizations to a model.

        Args:
            model: Model to optimize
            model_name: Name identifier for the model

        Returns:
            Optimized model
        """
        logger.info(f"Optimizing model: {model_name}")

        # Apply optimizations in sequence
        optimized_model = model

        # 1. JIT compilation (for CPU inference)
        if self.optimization_config['enable_jit']:
            optimized_model = self._apply_jit_compilation(optimized_model)

        # 2. Mixed precision (FP16)
        if self.optimization_config['enable_fp16'] and torch.cuda.is_available():
            optimized_model = self._apply_mixed_precision(optimized_model)

        # 3. Memory optimizations
        optimized_model = self._apply_memory_optimizations(optimized_model)

        # 4. Hardware-specific optimizations
        optimized_model = self._apply_hardware_optimizations(optimized_model)

        # Cache the optimized model
        self.model_cache[model_name] = optimized_model

        logger.info(f"Model {model_name} optimization completed")
        return optimized_model

    def _apply_jit_compilation(self, model: nn.Module) -> nn.Module:
        """Apply JIT compilation for CPU optimization."""
        try:
            # Set model to evaluation mode
            model.eval()

            # Trace the model with a sample input
            sample_input = self._get_sample_input(model)

            if sample_input is not None:
                with torch.no_grad():
                    traced_model = torch.jit.trace(model, sample_input)
                logger.info("JIT compilation applied")
                return traced_model
            else:
                logger.warning("Could not create sample input for JIT compilation")
                return model

        except Exception as e:
            logger.warning(f"JIT compilation failed: {e}")
            return model

    def _apply_mixed_precision(self, model: nn.Module) -> nn.Module:
        """Apply mixed precision (FP16) optimization."""
        try:
            model.half()  # Convert to FP16
            model = model.cuda()  # Move to GPU
            logger.info("Mixed precision (FP16) applied")
            return model
        except Exception as e:
            logger.warning(f"Mixed precision failed: {e}")
            return model

    def _apply_memory_optimizations(self, model: nn.Module) -> nn.Module:
        """Apply memory optimizations."""
        # Disable gradient computation
        for param in model.parameters():
            param.requires_grad = False

        # Enable memory efficient evaluation
        model.eval()

        # Use memory pinning if on GPU
        if torch.cuda.is_available():
            model = model.pin_memory()

        return model

    def _apply_hardware_optimizations(self, model: nn.Module) -> nn.Module:
        """Apply hardware-specific optimizations."""
        if torch.cuda.is_available():
            # cuDNN optimizations
            torch.backends.cudnn.benchmark = True
            torch.backends.cudnn.enabled = True

            # Disable gradient computation for inference
            torch.set_grad_enabled(False)

        return model

    def _get_sample_input(self, model: nn.Module) -> Optional[torch.Tensor]:
        """Generate sample input for model tracing."""
        # This is a simplified approach - in practice, you'd need
        # to know the expected input shape for each model type

        # Try common input shapes
        sample_shapes = [
            (1, 768),      # Text embeddings
            (1, 3, 224, 224),  # Images
            (1, 512),      # General embeddings
        ]

        for shape in sample_shapes:
            try:
                sample_input = torch.randn(*shape)
                # Test if model accepts this input
                with torch.no_grad():
                    _ = model(sample_input)
                return sample_input
            except Exception:
                continue

        return None

    @lru_cache(maxsize=1000)
    def cached_inference(self, model_name: str, input_hash: str, inputs: Tuple) -> Any:
        """
        Perform cached inference.

        Args:
            model_name: Name of the model
            input_hash: Hash of inputs for caching
            inputs: Model inputs

        Returns:
            Cached inference result
        """
        if not self.optimization_config['enable_caching']:
            return self._direct_inference(model_name, inputs)

        # Check cache
        cache_key = f"{model_name}_{input_hash}"
        if cache_key in self.result_cache:
            self.performance_stats['cache_hits'] += 1
            return self.result_cache[cache_key]

        # Perform inference
        self.performance_stats['cache_misses'] += 1
        result = self._direct_inference(model_name, inputs)

        # Cache result (with size limit)
        if len(self.result_cache) < self.optimization_config['cache_size']:
            self.result_cache[cache_key] = result

        return result

    def _direct_inference(self, model_name: str, inputs: Tuple) -> Any:
        """Perform direct model inference."""
        start_time = time.time()

        model = self.model_cache.get(model_name)
        if model is None:
            raise ValueError(f"Model {model_name} not found in cache")

        # Convert inputs back to tensors
        tensor_inputs = []
        for inp in inputs:
            if isinstance(inp, torch.Tensor):
                tensor_inputs.append(inp)
            else:
                tensor_inputs.append(torch.tensor(inp))

        # Perform inference
        with torch.no_grad():
            outputs = model(*tensor_inputs)

        # Update performance stats
        inference_time = time.time() - start_time
        self.performance_stats['inference_count'] += 1
        self.performance_stats['total_inference_time'] += inference_time
        self.performance_stats['avg_inference_time'] = (
            self.performance_stats['total_inference_time'] /
            self.performance_stats['inference_count']
        )

        return outputs

    def batch_inference(self, model_name: str, batch_inputs: List[Tuple],
                       max_batch_size: Optional[int] = None) -> List[Any]:
        """
        Perform batch inference for efficiency.

        Args:
            model_name: Model name
            batch_inputs: List of input tuples
            max_batch_size: Maximum batch size

        Returns:
            List of inference results
        """
        max_batch_size = max_batch_size or self.optimization_config['max_batch_size']

        results = []

        # Process in batches
        for i in range(0, len(batch_inputs), max_batch_size):
            batch = batch_inputs[i:i + max_batch_size]

            # Batch processing (simplified - assumes tensor inputs)
            try:
                batched_tensors = []
                for inp_tuple in batch:
                    tensors = [torch.tensor(inp) for inp in inp_tuple]
                    batched_tensors.append(tensors)

                # Stack tensors if possible
                if len(batched_tensors) > 1 and all(len(t) == len(batched_tensors[0]) for t in batched_tensors):
                    stacked_inputs = []
                    for j in range(len(batched_tensors[0])):
                        tensor_list = [batch[j] for batch in batched_tensors]
                        if all(t.shape == tensor_list[0].shape for t in tensor_list):
                            stacked = torch.stack(tensor_list)
                            stacked_inputs.append(stacked)
                        else:
                            # Can't stack, process individually
                            individual_results = []
                            for inp_tuple in batch:
                                result = self.cached_inference(model_name, hash(str(inp_tuple)), inp_tuple)
                                individual_results.append(result)
                            results.extend(individual_results)
                            break
                    else:
                        # Perform batched inference
                        batch_result = self._direct_inference(model_name, tuple(stacked_inputs))
                        results.extend(batch_result)
                else:
                    # Process individually
                    for inp_tuple in batch:
                        result = self.cached_inference(model_name, hash(str(inp_tuple)), inp_tuple)
                        results.append(result)

            except Exception as e:
                logger.warning(f"Batch inference failed, falling back to individual: {e}")
                # Fallback to individual processing
                for inp_tuple in batch:
                    result = self.cached_inference(model_name, hash(str(inp_tuple)), inp_tuple)
                    results.append(result)

        return results

    def async_inference(self, model_name: str, inputs: Tuple) -> Any:
        """
        Perform asynchronous inference.

        Args:
            model_name: Model name
            inputs: Model inputs

        Returns:
            Future result
        """
        future = self.executor.submit(
            self.cached_inference,
            model_name,
            hash(str(inputs)),
            inputs
        )
        return future

    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics.

        Returns:
            Performance metrics
        """
        stats = self.performance_stats.copy()

        # Add cache efficiency
        total_cache_requests = stats['cache_hits'] + stats['cache_misses']
        if total_cache_requests > 0:
            stats['cache_hit_rate'] = stats['cache_hits'] / total_cache_requests
        else:
            stats['cache_hit_rate'] = 0.0

        # Add hardware stats
        stats['hardware'] = self.hardware_monitor.get_stats()

        return stats

    def clear_cache(self):
        """Clear inference cache."""
        self.result_cache.clear()
        logger.info("Inference cache cleared")

    def optimize_memory_usage(self):
        """Optimize memory usage."""
        # Clear unused cached models
        current_memory = psutil.virtual_memory().percent

        if current_memory > 80:  # High memory usage
            # Clear half of the cache
            cache_items = list(self.result_cache.items())
            for i in range(len(cache_items) // 2):
                key, _ = cache_items[i]
                del self.result_cache[key]

            # Force garbage collection
            import gc
            gc.collect()

            logger.info("Memory optimization applied")

    def adaptive_batching(self, model_name: str, inputs_list: List[Tuple]) -> List[Any]:
        """
        Adaptively determine optimal batch size based on hardware.

        Args:
            model_name: Model name
            inputs_list: List of inputs

        Returns:
            Batched inference results
        """
        # Monitor hardware resources
        hardware_stats = self.hardware_monitor.get_stats()

        # Adjust batch size based on available memory
        gpu_memory_gb = hardware_stats.get('gpu_memory_free_gb', 0)
        available_memory_ratio = gpu_memory_gb / self.optimization_config['gpu_memory_limit_gb']

        if available_memory_ratio > 0.8:
            optimal_batch_size = self.optimization_config['max_batch_size']
        elif available_memory_ratio > 0.5:
            optimal_batch_size = self.optimization_config['max_batch_size'] // 2
        else:
            optimal_batch_size = 1  # Process individually

        logger.debug(f"Adaptive batching: using batch size {optimal_batch_size}")

        return self.batch_inference(model_name, inputs_list, optimal_batch_size)


class HardwareMonitor:
    """
    Monitor hardware resources for optimization decisions.
    """

    def __init__(self):
        """Initialize hardware monitor."""
        self.last_update = 0
        self.cached_stats = {}
        self.update_interval = 5  # Update every 5 seconds

    def get_stats(self) -> Dict[str, Any]:
        """
        Get current hardware statistics.

        Returns:
            Hardware resource statistics
        """
        current_time = time.time()

        # Use cached stats if recent
        if current_time - self.last_update < self.update_interval and self.cached_stats:
            return self.cached_stats

        stats = {}

        # CPU stats
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()

        stats.update({
            'cpu_percent': cpu_percent,
            'memory_total_gb': memory.total / (1024**3),
            'memory_used_gb': memory.used / (1024**3),
            'memory_free_gb': memory.available / (1024**3),
            'memory_percent': memory.percent
        })

        # GPU stats
        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu = gpus[0]  # Primary GPU
                stats.update({
                    'gpu_memory_total_gb': gpu.memoryTotal / 1024,
                    'gpu_memory_used_gb': gpu.memoryUsed / 1024,
                    'gpu_memory_free_gb': gpu.memoryFree / 1024,
                    'gpu_utilization': gpu.load * 100
                })
        except Exception:
            # GPU monitoring not available
            pass

        # Update cache
        self.cached_stats = stats
        self.last_update = current_time

        return stats







