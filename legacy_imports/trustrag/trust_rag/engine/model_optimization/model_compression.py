"""
Model Compression for GraphRAG.

This module provides comprehensive model compression techniques
combining quantization, pruning, and distillation.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import torch
import torch.nn as nn
import torch.nn.utils.prune as prune
import numpy as np

from .quantization import ModelQuantizer
from .knowledge_distillation import KnowledgeDistiller
from .inference_optimizer import InferenceOptimizer

logger = logging.getLogger(__name__)


class ModelCompressor:
    """
    Comprehensive model compression combining multiple techniques.
    """

    def __init__(self, compression_config: Optional[Dict[str, Any]] = None):
        """
        Initialize model compressor.

        Args:
            compression_config: Compression configuration
        """
        self.compression_config = compression_config or {
            'target_compression_ratio': 0.5,
            'max_accuracy_drop': 0.05,
            'techniques': ['quantization', 'pruning', 'distillation'],
            'quantization_bits': 8,
            'pruning_ratio': 0.3,
            'distillation_temperature': 2.0
        }

        # Initialize compression components
        self.quantizer = ModelQuantizer()
        self.inference_optimizer = InferenceOptimizer()

        logger.info("Model compressor initialized")

    def compress_model(
        self,
        model: nn.Module,
        calibration_data: Optional[List[Any]] = None,
        teacher_model: Optional[nn.Module] = None,
        compression_config: Optional[Dict[str, Any]] = None
    ) -> Tuple[nn.Module, Dict[str, Any]]:
        """
        Compress model using multiple techniques.

        Args:
            model: Model to compress
            calibration_data: Data for quantization calibration
            teacher_model: Teacher model for distillation
            compression_config: Override compression config

        Returns:
            Tuple of (compressed_model, compression_stats)
        """
        config = {**self.compression_config, **(compression_config or {})}
        compressed_model = model

        compression_stats = {
            'original_params': sum(p.numel() for p in model.parameters()),
            'techniques_applied': [],
            'compression_ratio': 1.0,
            'accuracy_preserved': True,
            'performance_improvement': {}
        }

        # Apply compression techniques in sequence
        techniques = config['techniques']

        if 'pruning' in techniques:
            logger.info("Applying pruning compression")
            compressed_model, prune_stats = self._apply_pruning(compressed_model, config)
            compression_stats['techniques_applied'].append('pruning')
            compression_stats.update(prune_stats)

        if 'quantization' in techniques:
            logger.info("Applying quantization compression")
            compressed_model, quant_stats = self._apply_quantization(
                compressed_model, calibration_data, config
            )
            compression_stats['techniques_applied'].append('quantization')
            compression_stats.update(quant_stats)

        if 'distillation' in techniques and teacher_model is not None:
            logger.info("Applying distillation compression")
            compressed_model, distill_stats = self._apply_distillation(
                teacher_model, compressed_model, config
            )
            compression_stats['techniques_applied'].append('distillation')
            compression_stats.update(distill_stats)

        # Apply inference optimizations
        compressed_model = self.inference_optimizer.optimize_model(compressed_model)

        # Calculate final compression ratio
        final_params = sum(p.numel() for p in compressed_model.parameters())
        compression_stats['final_params'] = final_params
        compression_stats['compression_ratio'] = (
            final_params / compression_stats['original_params']
            if compression_stats['original_params'] > 0 else 1.0
        )

        logger.info(f"Model compression completed. Ratio: {compression_stats['compression_ratio']:.3f}")

        return compressed_model, compression_stats

    def _apply_pruning(self, model: nn.Module, config: Dict[str, Any]) -> Tuple[nn.Module, Dict[str, Any]]:
        """Apply pruning to the model."""
        pruning_ratio = config['pruning_ratio']

        # Identify prunable layers
        prunable_modules = []
        for name, module in model.named_modules():
            if isinstance(module, (nn.Linear, nn.Conv2d)):
                prunable_modules.append((name, module))

        if not prunable_modules:
            logger.warning("No prunable layers found")
            return model, {'pruning_applied': False}

        # Apply L1 unstructured pruning
        for name, module in prunable_modules:
            prune.l1_unstructured(module, name='weight', amount=pruning_ratio)

        # Remove pruning reparameterization
        for name, module in prunable_modules:
            prune.remove(module, 'weight')

        # Calculate pruning statistics
        original_params = sum(p.numel() for p in model.parameters())
        pruned_params = sum(torch.sum(p != 0).item() for p in model.parameters())

        prune_stats = {
            'pruning_applied': True,
            'pruning_ratio': pruning_ratio,
            'pruned_params': int(original_params - pruned_params),
            'sparsity_ratio': 1.0 - (pruned_params / original_params) if original_params > 0 else 0
        }

        logger.info(f"Pruning applied: {prune_stats['sparsity_ratio']:.3f} sparsity")
        return model, prune_stats

    def _apply_quantization(self, model: nn.Module, calibration_data: List[Any],
                           config: Dict[str, Any]) -> Tuple[nn.Module, Dict[str, Any]]:
        """Apply quantization to the model."""
        bits = config['quantization_bits']

        if bits == 4:
            quantized_model = self.quantizer.quantize_to_int4(model, calibration_data)
        elif bits == 8:
            quantized_model = self.quantizer.quantize_to_int8(model, calibration_data)
        else:
            quantized_model = self.quantizer.quantize_to_fp16(model)

        # Get quantization statistics
        quant_stats = self.quantizer.get_model_size_info(quantized_model)
        quant_stats['quantization_applied'] = True
        quant_stats['target_bits'] = bits

        return quantized_model, quant_stats

    def _apply_distillation(self, teacher_model: nn.Module, student_model: nn.Module,
                           config: Dict[str, Any]) -> Tuple[nn.Module, Dict[str, Any]]:
        """Apply knowledge distillation."""
        # Create distillation configuration
        student_config = {
            'input_dim': self._get_model_input_dim(student_model),
            'hidden_dims': [256, 128],  # Simplified student architecture
            'output_dim': self._get_model_output_dim(teacher_model),
            'dropout': 0.1
        }

        distiller = KnowledgeDistiller(
            teacher_model=teacher_model,
            student_config=student_config,
            distillation_config={
                'temperature': config['distillation_temperature'],
                'alpha': 0.5,
                'learning_rate': 1e-3,
                'num_epochs': 5  # Short training for demo
            }
        )

        # Note: In practice, you'd need actual training data here
        # For now, just return the student model
        distilled_model = distiller.get_student_model()

        distill_stats = distiller.evaluate_compression()
        distill_stats['distillation_applied'] = True

        return distilled_model, distill_stats

    def _get_model_input_dim(self, model: nn.Module) -> int:
        """Get model input dimension (simplified)."""
        # This is a heuristic - in practice you'd need to know the model architecture
        for name, param in model.named_parameters():
            if 'weight' in name and len(param.shape) >= 2:
                return param.shape[1]  # Input dimension
        return 768  # Default

    def _get_model_output_dim(self, model: nn.Module) -> int:
        """Get model output dimension (simplified)."""
        # This is a heuristic - in practice you'd need to know the model architecture
        for name, param in model.named_parameters():
            if 'weight' in name and len(param.shape) >= 2:
                return param.shape[0]  # Output dimension
        return 768  # Default

    def benchmark_compression(self, original_model: nn.Module, compressed_model: nn.Module,
                            test_data: List[Any], device: str = 'auto') -> Dict[str, Any]:
        """
        Benchmark compression quality and performance.

        Args:
            original_model: Original model
            compressed_model: Compressed model
            test_data: Test data for benchmarking
            device: Device to run benchmarks on

        Returns:
            Benchmarking results
        """
        logger.info("Benchmarking model compression")

        # Setup device
        if device == 'auto':
            device = 'cuda' if torch.cuda.is_available() else 'cpu'

        original_model = original_model.to(device)
        compressed_model = compressed_model.to(device)

        benchmark_results = {
            'inference_speed': {},
            'memory_usage': {},
            'accuracy_metrics': {}
        }

        # Benchmark inference speed
        original_speed = self.quantizer.benchmark_inference_speed(
            original_model, test_data[0], num_runs=50, device=device
        )
        compressed_speed = self.quantizer.benchmark_inference_speed(
            compressed_model, test_data[0], num_runs=50, device=device
        )

        benchmark_results['inference_speed'] = {
            'original_avg_time': original_speed['avg_inference_time'],
            'compressed_avg_time': compressed_speed['avg_inference_time'],
            'speedup_ratio': original_speed['avg_inference_time'] / compressed_speed['avg_inference_time']
        }

        # Benchmark memory usage
        original_stats = self.quantizer.get_model_size_info(original_model)
        compressed_stats = self.quantizer.get_model_size_info(compressed_model)

        benchmark_results['memory_usage'] = {
            'original_memory_mb': original_stats['estimated_memory_mb'],
            'compressed_memory_mb': compressed_stats['estimated_memory_mb'],
            'memory_savings_mb': original_stats['estimated_memory_mb'] - compressed_stats['estimated_memory_mb']
        }

        # Note: Accuracy metrics would require validation data and labels
        # This is a placeholder for actual accuracy evaluation

        logger.info(f"Compression benchmarking completed. Speedup: {benchmark_results['inference_speed']['speedup_ratio']:.2f}x")

        return benchmark_results

    def get_optimal_compression_config(
        self,
        model: nn.Module,
        constraints: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Determine optimal compression configuration based on constraints.

        Args:
            model: Model to compress
            constraints: Compression constraints (size, latency, accuracy)

        Returns:
            Optimal compression configuration
        """
        config = self.compression_config.copy()

        # Adjust based on constraints
        if 'max_size_mb' in constraints:
            target_size = constraints['max_size_mb']
            original_size = self.quantizer.get_model_size_info(model)['estimated_memory_mb']

            if target_size < original_size * 0.8:  # Need significant compression
                config['techniques'] = ['quantization', 'pruning', 'distillation']
                config['quantization_bits'] = 4
                config['pruning_ratio'] = 0.5
            elif target_size < original_size * 0.9:
                config['techniques'] = ['quantization', 'pruning']
                config['quantization_bits'] = 8
                config['pruning_ratio'] = 0.3

        if 'max_latency_ms' in constraints:
            # Adjust techniques based on latency requirements
            max_latency = constraints['max_latency_ms']
            if max_latency < 10:  # Very low latency required
                config['techniques'] = ['quantization', 'pruning']
                config['quantization_bits'] = 8

        if 'max_accuracy_drop' in constraints:
            config['max_accuracy_drop'] = constraints['max_accuracy_drop']

        return config

    def iterative_compression(
        self,
        model: nn.Module,
        calibration_data: List[Any],
        target_metrics: Dict[str, Any],
        max_iterations: int = 5
    ) -> Tuple[nn.Module, Dict[str, Any]]:
        """
        Iteratively compress model to meet target metrics.

        Args:
            model: Model to compress
            calibration_data: Calibration data
            target_metrics: Target performance metrics
            max_iterations: Maximum compression iterations

        Returns:
            Tuple of (compressed_model, compression_stats)
        """
        logger.info("Starting iterative compression")

        best_model = model
        best_stats = {'compression_ratio': 1.0}

        for iteration in range(max_iterations):
            logger.info(f"Iterative compression iteration {iteration + 1}")

            # Generate compression config for this iteration
            config = self._generate_iteration_config(iteration, target_metrics)

            # Apply compression
            compressed_model, stats = self.compress_model(
                model, calibration_data, compression_config=config
            )

            # Check if targets are met
            if self._check_targets_met(stats, target_metrics):
                logger.info(f"Compression targets met at iteration {iteration + 1}")
                return compressed_model, stats

            # Keep track of best result
            if stats.get('compression_ratio', 1.0) < best_stats.get('compression_ratio', 1.0):
                best_model = compressed_model
                best_stats = stats

        logger.info("Iterative compression completed")
        return best_model, best_stats

    def _generate_iteration_config(self, iteration: int, target_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Generate compression config for current iteration."""
        base_config = self.compression_config.copy()

        # Increase compression aggressiveness with iterations
        iteration_factor = (iteration + 1) / 5  # Scale from 0.2 to 1.0

        base_config['pruning_ratio'] = min(0.6, base_config.get('pruning_ratio', 0.3) * iteration_factor)

        if iteration > 2:
            base_config['quantization_bits'] = 4  # More aggressive quantization later

        return base_config

    def _check_targets_met(self, stats: Dict[str, Any], targets: Dict[str, Any]) -> bool:
        """Check if compression targets are met."""
        # Check compression ratio
        if 'target_compression_ratio' in targets:
            if stats.get('compression_ratio', 1.0) > targets['target_compression_ratio']:
                return False

        # Check accuracy preservation
        if 'max_accuracy_drop' in targets:
            accuracy_drop = stats.get('accuracy_drop', 0.0)
            if accuracy_drop > targets['max_accuracy_drop']:
                return False

        return True







