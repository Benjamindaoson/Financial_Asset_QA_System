"""
Model Quantization for GraphRAG.

This module provides quantization techniques (INT4, INT8, FP16)
to reduce model size and improve inference speed.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import torch
import torch.nn as nn
from torch.quantization import QuantStub, DeQuantStub
import numpy as np

logger = logging.getLogger(__name__)


class ModelQuantizer:
    """
    Model quantizer for reducing model size and improving inference speed.
    """

    def __init__(self, quantization_config: Optional[Dict[str, Any]] = None):
        """
        Initialize model quantizer.

        Args:
            quantization_config: Quantization configuration
        """
        self.quantization_config = quantization_config or {
            'method': 'dynamic',  # static, dynamic, qat
            'dtype': torch.qint8,  # torch.qint8, torch.quint8, etc.
            'observer': 'histogram',  # min_max, moving_average, histogram
            'reduce_range': False,
            'quantize_embeddings': False,
            'fuse_modules': True
        }

        self.quantized_models = {}
        logger.info("Model quantizer initialized")

    def quantize_model(
        self,
        model: nn.Module,
        calibration_data: Optional[List[Any]] = None,
        config_override: Optional[Dict[str, Any]] = None
    ) -> nn.Module:
        """
        Quantize a model using the specified configuration.

        Args:
            model: Model to quantize
            calibration_data: Data for calibration (required for static quantization)
            config_override: Override quantization config

        Returns:
            Quantized model
        """
        config = {**self.quantization_config, **(config_override or {})}

        method = config['method']

        if method == 'dynamic':
            return self._dynamic_quantization(model, config)
        elif method == 'static':
            return self._static_quantization(model, calibration_data, config)
        elif method == 'qat':
            return self._quantization_aware_training(model, config)
        else:
            raise ValueError(f"Unknown quantization method: {method}")

    def _dynamic_quantization(self, model: nn.Module, config: Dict[str, Any]) -> nn.Module:
        """Apply dynamic quantization."""
        logger.info("Applying dynamic quantization")

        # Prepare model for quantization
        model.eval()

        # Specify quantization configuration
        qconfig = torch.quantization.default_dynamic_qconfig

        # Apply quantization
        quantized_model = torch.quantization.quantize_dynamic(
            model,
            qconfig_spec=qconfig,
            dtype=config['dtype']
        )

        logger.info("Dynamic quantization completed")
        return quantized_model

    def _static_quantization(self, model: nn.Module, calibration_data: List[Any],
                           config: Dict[str, Any]) -> nn.Module:
        """Apply static quantization."""
        logger.info("Applying static quantization")

        if calibration_data is None:
            raise ValueError("Calibration data required for static quantization")

        # Prepare model for quantization
        model.eval()

        # Fuse modules if requested
        if config.get('fuse_modules', True):
            model = self._fuse_modules(model)

        # Add quantization stubs
        model = self._add_quant_stubs(model)

        # Specify quantization configuration
        if config['observer'] == 'histogram':
            model.qconfig = torch.quantization.get_default_qconfig('fbgemm')
        else:
            model.qconfig = torch.quantization.default_qconfig

        # Prepare for quantization
        torch.quantization.prepare(model, inplace=True)

        # Calibrate with data
        logger.info("Calibrating with data...")
        self._calibrate_model(model, calibration_data)

        # Convert to quantized model
        torch.quantization.convert(model, inplace=True)

        logger.info("Static quantization completed")
        return model

    def _quantization_aware_training(self, model: nn.Module, config: Dict[str, Any]) -> nn.Module:
        """Apply quantization-aware training."""
        logger.info("Applying quantization-aware training")

        # Fuse modules
        model = self._fuse_modules(model)

        # Add quantization stubs
        model = self._add_quant_stubs(model)

        # Set quantization config
        model.qconfig = torch.quantization.get_default_qat_qconfig('fbgemm')

        # Prepare for QAT
        torch.quantization.prepare_qat(model, inplace=True)

        # Note: In practice, you would train the model here
        logger.warning("QAT requires training - returning prepared model")

        return model

    def _fuse_modules(self, model: nn.Module) -> nn.Module:
        """Fuse modules for better quantization."""
        # Common fusion patterns
        fusion_patterns = [
            [nn.Conv2d, nn.BatchNorm2d],
            [nn.Conv2d, nn.BatchNorm2d, nn.ReLU],
            [nn.Linear, nn.ReLU],
            [nn.BatchNorm2d, nn.ReLU]
        ]

        # Apply fusions (simplified - in practice would be more comprehensive)
        for pattern in fusion_patterns:
            try:
                torch.quantization.fuse_modules(model, pattern, inplace=True)
            except Exception:
                continue  # Skip if fusion not applicable

        return model

    def _add_quant_stubs(self, model: nn.Module) -> nn.Module:
        """Add quantization stubs to model."""
        # This is a simplified implementation
        # In practice, you would add QuantStub and DeQuantStub strategically

        # Wrap the model to add quantization stubs
        class QuantizedModel(nn.Module):
            def __init__(self, model):
                super().__init__()
                self.quant = QuantStub()
                self.model = model
                self.dequant = DeQuantStub()

            def forward(self, x):
                x = self.quant(x)
                x = self.model(x)
                x = self.dequant(x)
                return x

        return QuantizedModel(model)

    def _calibrate_model(self, model: nn.Module, calibration_data: List[Any]):
        """Calibrate quantized model with data."""
        model.eval()

        with torch.no_grad():
            for i, data in enumerate(calibration_data):
                if i >= 100:  # Limit calibration samples
                    break

                # Forward pass for calibration
                try:
                    _ = model(data)
                except Exception as e:
                    logger.warning(f"Calibration failed for sample {i}: {e}")
                    continue

        logger.info("Model calibration completed")

    def quantize_to_int4(self, model: nn.Module, calibration_data: Optional[List[Any]] = None) -> nn.Module:
        """
        Quantize model to INT4 precision.

        Args:
            model: Model to quantize
            calibration_data: Calibration data

        Returns:
            INT4 quantized model
        """
        logger.info("Quantizing to INT4")

        # For INT4 quantization, we'll use dynamic quantization with custom config
        # Note: PyTorch doesn't natively support INT4, this is a simplified approach

        config = {
            'method': 'dynamic',
            'dtype': torch.qint8,  # Closest available
            'custom_quantization': 'int4_approximation'
        }

        quantized_model = self.quantize_model(model, calibration_data, config)

        # Add metadata about INT4 approximation
        quantized_model.quantization_info = {
            'target_precision': 'INT4',
            'actual_precision': 'INT8',
            'method': 'approximation'
        }

        return quantized_model

    def quantize_to_int8(self, model: nn.Module, calibration_data: Optional[List[Any]] = None) -> nn.Module:
        """
        Quantize model to INT8 precision.

        Args:
            model: Model to quantize
            calibration_data: Calibration data

        Returns:
            INT8 quantized model
        """
        logger.info("Quantizing to INT8")

        config = {
            'method': 'dynamic',
            'dtype': torch.qint8
        }

        quantized_model = self.quantize_model(model, calibration_data, config)
        quantized_model.quantization_info = {
            'target_precision': 'INT8',
            'method': 'dynamic'
        }

        return quantized_model

    def quantize_to_fp16(self, model: nn.Module) -> nn.Module:
        """
        Convert model to FP16 precision.

        Args:
            model: Model to convert

        Returns:
            FP16 model
        """
        logger.info("Converting to FP16")

        # Convert model to half precision
        model.half()

        # Move to GPU if available for FP16
        if torch.cuda.is_available():
            model = model.cuda()

        model.fp16_info = {
            'precision': 'FP16',
            'device': 'cuda' if torch.cuda.is_available() else 'cpu'
        }

        return model

    def get_model_size_info(self, model: nn.Module) -> Dict[str, Any]:
        """
        Get model size information.

        Args:
            model: Model to analyze

        Returns:
            Size information
        """
        # Calculate parameter count
        total_params = sum(p.numel() for p in model.parameters())
        trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)

        # Estimate memory usage (rough calculation)
        param_memory = total_params * 4  # Assume 4 bytes per parameter (FP32)

        # Get quantization info if available
        quant_info = getattr(model, 'quantization_info', None) or getattr(model, 'fp16_info', None)

        info = {
            'total_parameters': total_params,
            'trainable_parameters': trainable_params,
            'estimated_memory_mb': param_memory / (1024 * 1024),
            'quantization_info': quant_info
        }

        return info

    def optimize_for_inference(self, model: nn.Module, device: str = 'cpu') -> nn.Module:
        """
        Optimize model for inference.

        Args:
            model: Model to optimize
            device: Target device

        Returns:
            Optimized model
        """
        logger.info(f"Optimizing model for inference on {device}")

        model.eval()

        # JIT compilation for CPU
        if device == 'cpu':
            try:
                model = torch.jit.script(model)
                logger.info("Model JIT compiled for CPU")
            except Exception as e:
                logger.warning(f"JIT compilation failed: {e}")

        # GPU optimizations
        elif device.startswith('cuda'):
            # Enable cuDNN optimizations
            torch.backends.cudnn.benchmark = True
            torch.backends.cudnn.enabled = True

            # Move to GPU
            model = model.cuda()

        # Memory optimizations
        for param in model.parameters():
            param.requires_grad = False

        return model

    def benchmark_inference_speed(
        self,
        model: nn.Module,
        sample_input: Any,
        num_runs: int = 100,
        device: str = 'cpu'
    ) -> Dict[str, float]:
        """
        Benchmark model inference speed.

        Args:
            model: Model to benchmark
            sample_input: Sample input for benchmarking
            num_runs: Number of benchmark runs
            device: Device to run on

        Returns:
            Benchmark results
        """
        logger.info(f"Benchmarking inference speed on {device}")

        model.eval()

        # Warmup
        with torch.no_grad():
            for _ in range(10):
                _ = model(sample_input)

        # Benchmark
        import time

        if device.startswith('cuda'):
            torch.cuda.synchronize()

        start_time = time.time()

        with torch.no_grad():
            for _ in range(num_runs):
                _ = model(sample_input)

        if device.startswith('cuda'):
            torch.cuda.synchronize()

        end_time = time.time()

        total_time = end_time - start_time
        avg_time = total_time / num_runs
        throughput = num_runs / total_time

        results = {
            'total_time': total_time,
            'avg_inference_time': avg_time,
            'throughput': throughput,
            'device': device,
            'num_runs': num_runs
        }

        logger.info(".4f")
        logger.info(".2f")
        return results







