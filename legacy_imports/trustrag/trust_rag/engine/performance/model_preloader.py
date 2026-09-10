"""
Model Preloader for GraphRAG.

This module provides intelligent model preloading to reduce cold start times
and optimize inference performance.
"""

import logging
from typing import Dict, List, Any, Optional, Callable, Union
import time
import threading
import torch
from pathlib import Path
import psutil
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class ModelPreloader:
    """
    Intelligent model preloader for optimizing cold start times and inference performance.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize model preloader.

        Args:
            config: Preloader configuration
        """
        self.config = config or {}

        # Performance targets
        self.target_cold_start_time = self.config.get('target_cold_start_time', 3.0)  # seconds

        # Resource limits
        self.max_memory_usage = self.config.get('max_memory_usage', 0.7)  # 70% memory
        self.max_cpu_usage = self.config.get('max_cpu_usage', 0.8)  # 80% CPU

        # Model registry
        self.models: Dict[str, Any] = {}
        self.model_configs: Dict[str, Dict[str, Any]] = {}

        # Preloading settings
        self.preload_threads = self.config.get('preload_threads', 2)
        self.warmup_queries = self.config.get('warmup_queries', [])
        self.enable_quantization = self.config.get('enable_quantization', True)

        # Device management
        self.device = self.config.get('device', 'cuda' if torch.cuda.is_available() else 'cpu')

        # Memory management
        self.memory_tracker = {}
        self.executor = ThreadPoolExecutor(max_workers=self.preload_threads)

        # Predefined models for GraphRAG
        self._init_model_configs()

        logger.info(f"Model preloader initialized on {self.device}")

    def _init_model_configs(self):
        """Initialize model configurations for common GraphRAG models."""
        self.model_configs = {
            'embedding_model': {
                'model_name': 'sentence-transformers/all-MiniLM-L6-v2',
                'model_type': 'sentence_transformer',
                'priority': 'high',
                'memory_estimate': 100 * 1024 * 1024,  # 100MB
                'warmup_samples': ['This is a test query for warmup.', 'Another sample for embedding.']
            },
            'reranker_model': {
                'model_name': 'cross-encoder/ms-marco-MiniLM-L-6-v2',
                'model_type': 'cross_encoder',
                'priority': 'high',
                'memory_estimate': 50 * 1024 * 1024,  # 50MB
                'warmup_samples': [['query1', 'doc1'], ['query2', 'doc2']]
            },
            'text_generation_model': {
                'model_name': 'microsoft/DialoGPT-small',
                'model_type': 'generative',
                'priority': 'medium',
                'memory_estimate': 200 * 1024 * 1024,  # 200MB
                'warmup_samples': ['Hello, how are you?']
            },
            'vision_model': {
                'model_name': 'google/vit-base-patch16-224',
                'model_type': 'vision',
                'priority': 'low',
                'memory_estimate': 150 * 1024 * 1024,  # 150MB
                'warmup_samples': []  # Would need image tensors
            }
        }

    def preload_models(self, preload_config: Dict[str, Any]):
        """
        Preload models according to configuration.

        Args:
            preload_config: Preloading configuration
        """
        start_time = time.time()

        # Determine which models to preload
        models_to_preload = preload_config.get('models', ['embedding_model'])
        priority_order = preload_config.get('priority_order', ['high', 'medium', 'low'])

        # Sort models by priority
        model_priorities = {}
        for model_name in models_to_preload:
            if model_name in self.model_configs:
                model_priorities[model_name] = self.model_configs[model_name]['priority']

        # Group by priority
        models_by_priority = {}
        for priority in priority_order:
            models_by_priority[priority] = [
                model for model in models_to_preload
                if model_priorities.get(model) == priority
            ]

        # Preload models by priority
        total_preloaded = 0
        for priority in priority_order:
            priority_models = models_by_priority[priority]
            if priority_models:
                logger.info(f"Preloading {len(priority_models)} {priority}-priority models")
                preloaded_count = self._preload_models_batch(priority_models)
                total_preloaded += preloaded_count

        preload_time = time.time() - start_time

        # Check if cold start target is met
        cold_start_achieved = preload_time <= self.target_cold_start_time

        logger.info(f"Model preloading completed in {preload_time:.2f}s (target: {self.target_cold_start_time}s)")

        if not cold_start_achieved:
            logger.warning(f"Cold start time exceeded target: {preload_time:.2f}s > {self.target_cold_start_time}s")

        return {
            'total_models_preloaded': total_preloaded,
            'preload_time': preload_time,
            'cold_start_target_met': cold_start_achieved,
            'memory_usage': self._get_memory_usage()
        }

    def _preload_models_batch(self, model_names: List[str]) -> int:
        """Preload a batch of models."""
        preloaded_count = 0

        for model_name in model_names:
            try:
                # Check resource availability
                if not self._check_resource_availability(model_name):
                    logger.warning(f"Insufficient resources for {model_name}, skipping")
                    continue

                # Preload model
                model_info = self._preload_single_model(model_name)
                if model_info:
                    self.models[model_name] = model_info
                    preloaded_count += 1

                    logger.info(f"Preloaded model: {model_name}")

            except Exception as e:
                logger.error(f"Failed to preload model {model_name}: {e}")

        return preloaded_count

    def _preload_single_model(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Preload a single model."""
        if model_name not in self.model_configs:
            logger.warning(f"Unknown model: {model_name}")
            return None

        config = self.model_configs[model_name]
        start_time = time.time()

        try:
            model_info = {}

            if config['model_type'] == 'sentence_transformer':
                model_info = self._preload_sentence_transformer(config)
            elif config['model_type'] == 'cross_encoder':
                model_info = self._preload_cross_encoder(config)
            elif config['model_type'] == 'generative':
                model_info = self._preload_generative_model(config)
            elif config['model_type'] == 'vision':
                model_info = self._preload_vision_model(config)
            else:
                logger.warning(f"Unsupported model type: {config['model_type']}")
                return None

            # Record memory usage
            load_time = time.time() - start_time
            model_info.update({
                'load_time': load_time,
                'memory_estimate': config['memory_estimate'],
                'priority': config['priority']
            })

            # Perform warmup
            if config.get('warmup_samples'):
                self._warmup_model(model_name, model_info, config['warmup_samples'])

            return model_info

        except Exception as e:
            logger.error(f"Model loading failed for {model_name}: {e}")
            return None

    def _preload_sentence_transformer(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Preload sentence transformer model."""
        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(config['model_name'], device=self.device)
            return {
                'model': model,
                'type': 'sentence_transformer',
                'encode_func': lambda texts: model.encode(texts, convert_to_tensor=True)
            }

        except ImportError:
            logger.warning("sentence-transformers not available")
            return None

    def _preload_cross_encoder(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Preload cross-encoder model."""
        try:
            from sentence_transformers import CrossEncoder

            model = CrossEncoder(config['model_name'], device=self.device)
            return {
                'model': model,
                'type': 'cross_encoder',
                'predict_func': lambda pairs: model.predict(pairs)
            }

        except ImportError:
            logger.warning("sentence-transformers not available")
            return None

    def _preload_generative_model(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Preload generative model."""
        try:
            from transformers import AutoTokenizer, AutoModelForCausalLM

            tokenizer = AutoTokenizer.from_pretrained(config['model_name'])
            model = AutoModelForCausalLM.from_pretrained(config['model_name']).to(self.device)

            return {
                'model': model,
                'tokenizer': tokenizer,
                'type': 'generative',
                'generate_func': lambda text: self._generate_text(model, tokenizer, text)
            }

        except ImportError:
            logger.warning("transformers not available")
            return None

    def _preload_vision_model(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Preload vision model."""
        try:
            from transformers import ViTImageProcessor, ViTForImageClassification

            processor = ViTImageProcessor.from_pretrained(config['model_name'])
            model = ViTForImageClassification.from_pretrained(config['model_name']).to(self.device)

            return {
                'model': model,
                'processor': processor,
                'type': 'vision'
            }

        except ImportError:
            logger.warning("transformers not available")
            return None

    def _generate_text(self, model, tokenizer, text: str, max_length: int = 50) -> str:
        """Generate text using the model."""
        inputs = tokenizer(text, return_tensors="pt").to(self.device)
        outputs = model.generate(**inputs, max_length=max_length, num_return_sequences=1)
        return tokenizer.decode(outputs[0], skip_special_tokens=True)

    def _warmup_model(self, model_name: str, model_info: Dict[str, Any], warmup_samples: List[Any]):
        """Warm up a model with sample data."""
        try:
            warmup_start = time.time()

            if model_info['type'] == 'sentence_transformer':
                _ = model_info['encode_func'](warmup_samples)
            elif model_info['type'] == 'cross_encoder':
                _ = model_info['predict_func'](warmup_samples)
            elif model_info['type'] == 'generative':
                for sample in warmup_samples:
                    _ = model_info['generate_func'](sample)
            # Vision models would need image warmup

            warmup_time = time.time() - warmup_start
            logger.debug(f"Model {model_name} warmed up in {warmup_time:.2f}s")

        except Exception as e:
            logger.warning(f"Model warmup failed for {model_name}: {e}")

    def _check_resource_availability(self, model_name: str) -> bool:
        """Check if resources are available for model loading."""
        config = self.model_configs[model_name]
        estimated_memory = config['memory_estimate']

        # Check available memory
        memory = psutil.virtual_memory()
        available_memory = memory.available

        if available_memory < estimated_memory * 1.2:  # 20% buffer
            return False

        # Check memory usage percentage
        memory_usage = memory.percent / 100.0
        if memory_usage > self.max_memory_usage:
            return False

        # Check CPU usage
        cpu_usage = psutil.cpu_percent() / 100.0
        if cpu_usage > self.max_cpu_usage:
            return False

        return True

    def _get_memory_usage(self) -> Dict[str, Any]:
        """Get current memory usage."""
        memory = psutil.virtual_memory()
        return {
            'total_memory': memory.total,
            'available_memory': memory.available,
            'used_memory': memory.used,
            'memory_usage_percent': memory.percent
        }

    def get_model(self, model_name: str) -> Optional[Any]:
        """
        Get a preloaded model.

        Args:
            model_name: Name of the model

        Returns:
            Model instance or None if not loaded
        """
        model_info = self.models.get(model_name)
        return model_info['model'] if model_info else None

    def is_model_loaded(self, model_name: str) -> bool:
        """Check if a model is loaded."""
        return model_name in self.models

    def get_preloader_stats(self) -> Dict[str, Any]:
        """Get preloader statistics."""
        total_models = len(self.models)
        memory_usage = self._get_memory_usage()

        model_types = {}
        load_times = []

        for model_name, model_info in self.models.items():
            model_type = model_info['type']
            model_types[model_type] = model_types.get(model_type, 0) + 1

            if 'load_time' in model_info:
                load_times.append(model_info['load_time'])

        avg_load_time = sum(load_times) / len(load_times) if load_times else 0

        return {
            'total_models_loaded': total_models,
            'model_types': model_types,
            'avg_load_time': avg_load_time,
            'memory_usage': memory_usage,
            'device': self.device
        }

    def unload_model(self, model_name: str) -> bool:
        """
        Unload a model to free memory.

        Args:
            model_name: Name of the model to unload

        Returns:
            Success status
        """
        if model_name in self.models:
            del self.models[model_name]
            logger.info(f"Unloaded model: {model_name}")
            return True

        return False

    def optimize_for_inference(self, model_name: str):
        """
        Apply inference optimizations to a model.

        Args:
            model_name: Name of the model
        """
        if model_name not in self.models:
            logger.warning(f"Model {model_name} not loaded")
            return

        model_info = self.models[model_name]

        try:
            if self.enable_quantization and hasattr(model_info['model'], 'to'):
                # Apply quantization if available
                model_info['model'] = self._quantize_model(model_info['model'])
                logger.info(f"Applied quantization to {model_name}")

            # Set to evaluation mode
            if hasattr(model_info['model'], 'eval'):
                model_info['model'].eval()

        except Exception as e:
            logger.warning(f"Failed to optimize model {model_name}: {e}")

    def _quantize_model(self, model):
        """Apply quantization to a model."""
        try:
            # Dynamic quantization for better performance
            quantized_model = torch.quantization.quantize_dynamic(
                model, {torch.nn.Linear}, dtype=torch.qint8
            )
            return quantized_model
        except Exception as e:
            logger.warning(f"Quantization failed: {e}")
            return model

    def preload_on_demand(self, model_name: str) -> bool:
        """
        Preload a model on demand.

        Args:
            model_name: Name of the model to preload

        Returns:
            Success status
        """
        if self.is_model_loaded(model_name):
            return True

        try:
            model_info = self._preload_single_model(model_name)
            if model_info:
                self.models[model_name] = model_info
                self.optimize_for_inference(model_name)
                logger.info(f"On-demand preloaded model: {model_name}")
                return True

        except Exception as e:
            logger.error(f"On-demand preloading failed for {model_name}: {e}")

        return False

    def enable_memory_optimization(self):
        """Enable memory optimization features."""
        if torch.cuda.is_available():
            # Enable CUDA memory optimization
            torch.cuda.empty_cache()
            torch.cuda.set_per_process_memory_fraction(0.8)  # Use up to 80% of GPU memory

        logger.info("Memory optimization enabled")

    def get_recommendations(self) -> List[str]:
        """Get optimization recommendations."""
        recommendations = []
        stats = self.get_preloader_stats()

        memory_usage = stats['memory_usage']['memory_usage_percent'] / 100.0

        if memory_usage > 0.8:
            recommendations.append("High memory usage - consider unloading unused models")

        if stats['avg_load_time'] > 2.0:
            recommendations.append("Slow model loading - consider using faster storage or model quantization")

        if len(self.models) < 3:
            recommendations.append("Few models preloaded - consider preloading more frequently used models")

        return recommendations
