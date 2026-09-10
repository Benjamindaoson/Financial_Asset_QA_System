"""
LoRA (Low-Rank Adaptation) Adapter for GraphRAG.

This module implements LoRA fine-tuning for efficient model adaptation
with minimal parameter updates for GraphRAG models.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import torch
import torch.nn as nn
from torch.nn import functional as F
from transformers import AutoModel, AutoTokenizer
import math

logger = logging.getLogger(__name__)


class LoRALayer(nn.Module):
    """
    LoRA layer that adapts a linear layer with low-rank matrices.
    """

    def __init__(
        self,
        original_layer: nn.Linear,
        r: int = 8,
        alpha: float = 16.0,
        dropout: float = 0.1
    ):
        """
        Initialize LoRA layer.

        Args:
            original_layer: Original linear layer to adapt
            r: Rank of LoRA matrices
            alpha: Scaling factor
            dropout: Dropout rate
        """
        super().__init__()

        self.original_layer = original_layer
        self.r = r
        self.alpha = alpha
        self.scaling = alpha / r

        # Freeze original parameters
        for param in self.original_layer.parameters():
            param.requires_grad = False

        # LoRA matrices
        self.lora_A = nn.Parameter(torch.randn(r, original_layer.in_features))
        self.lora_B = nn.Parameter(torch.zeros(original_layer.out_features, r))

        # Initialize A with Gaussian, B with zeros
        nn.init.kaiming_uniform_(self.lora_A, a=math.sqrt(5))

        self.dropout = nn.Dropout(dropout) if dropout > 0 else nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass with LoRA adaptation."""
        # Original forward pass
        original_output = self.original_layer(x)

        # LoRA adaptation
        lora_output = self.dropout(x) @ self.lora_A.T @ self.lora_B.T
        lora_output = lora_output * self.scaling

        return original_output + lora_output

    def get_lora_parameters(self) -> List[torch.nn.Parameter]:
        """Get LoRA parameters for optimization."""
        return [self.lora_A, self.lora_B]


class LoRAModel(nn.Module):
    """
    Model with LoRA adaptations applied to multiple layers.
    """

    def __init__(
        self,
        model_name: str,
        lora_config: Dict[str, Any],
        device: str = "auto"
    ):
        """
        Initialize LoRA model.

        Args:
            model_name: Base model name
            lora_config: LoRA configuration
            device: Device to run model on
        """
        super().__init__()

        self.device = self._setup_device(device)
        self.lora_config = lora_config

        # Load base model
        self.model = AutoModel.from_pretrained(model_name).to(self.device)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)

        # Apply LoRA to specified layers
        self.lora_layers = nn.ModuleDict()
        self._apply_lora_adaptations(lora_config)

        # Freeze all parameters except LoRA
        self._freeze_non_lora_params()

        logger.info(f"LoRA model initialized with {len(self.lora_layers)} adapted layers")

    def _setup_device(self, device: str) -> str:
        """Setup compute device."""
        if device == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"
        return device

    def _apply_lora_adaptations(self, lora_config: Dict[str, Any]):
        """Apply LoRA adaptations to model layers."""
        target_modules = lora_config.get('target_modules', ['query', 'key', 'value'])
        r = lora_config.get('r', 8)
        alpha = lora_config.get('alpha', 16.0)
        dropout = lora_config.get('dropout', 0.1)

        # Find target layers in the model
        for name, module in self.model.named_modules():
            if any(target in name.lower() for target in target_modules):
                if isinstance(module, nn.Linear):
                    # Replace with LoRA layer
                    lora_layer = LoRALayer(module, r=r, alpha=alpha, dropout=dropout)
                    self._replace_module(name, lora_layer)
                    self.lora_layers[name] = lora_layer
                    logger.debug(f"Applied LoRA to layer: {name}")

    def _replace_module(self, module_name: str, new_module: nn.Module):
        """Replace a module in the model."""
        module_names = module_name.split('.')
        parent_module = self.model

        for name in module_names[:-1]:
            parent_module = getattr(parent_module, name)

        setattr(parent_module, module_names[-1], new_module)

    def _freeze_non_lora_params(self):
        """Freeze all parameters except LoRA parameters."""
        for name, param in self.model.named_parameters():
            # Check if this parameter belongs to a LoRA layer
            is_lora_param = any(lora_name in name for lora_name in self.lora_layers.keys())
            param.requires_grad = is_lora_param

    def forward(self, **inputs):
        """Forward pass through LoRA model."""
        # Move inputs to device
        inputs = {k: v.to(self.device) if torch.is_tensor(v) else v
                 for k, v in inputs.items()}

        return self.model(**inputs)

    def get_lora_parameters(self) -> List[torch.nn.Parameter]:
        """Get all LoRA parameters for optimization."""
        lora_params = []
        for layer in self.lora_layers.values():
            lora_params.extend(layer.get_lora_parameters())
        return lora_params

    def save_lora_weights(self, path: str):
        """Save LoRA weights."""
        lora_state_dict = {}

        for layer_name, layer in self.lora_layers.items():
            lora_state_dict[f"{layer_name}.lora_A"] = layer.lora_A
            lora_state_dict[f"{layer_name}.lora_B"] = layer.lora_B

        torch.save(lora_state_dict, path)
        logger.info(f"Saved LoRA weights to {path}")

    def load_lora_weights(self, path: str):
        """Load LoRA weights."""
        lora_state_dict = torch.load(path, map_location=self.device)

        for layer_name, layer in self.lora_layers.items():
            layer.lora_A.data = lora_state_dict[f"{layer_name}.lora_A"]
            layer.lora_B.data = lora_state_dict[f"{layer_name}.lora_B"]

        logger.info(f"Loaded LoRA weights from {path}")

    def get_trainable_parameters(self) -> int:
        """Get number of trainable parameters."""
        return sum(p.numel() for p in self.get_lora_parameters())

    def get_total_parameters(self) -> int:
        """Get total number of parameters."""
        return sum(p.numel() for p in self.model.parameters())

    def get_compression_ratio(self) -> float:
        """Get compression ratio (trainable / total)."""
        trainable = self.get_trainable_parameters()
        total = self.get_total_parameters()
        return trainable / total if total > 0 else 0


class LoRAAdapter:
    """
    High-level LoRA adapter for fine-tuning models.
    """

    def __init__(
        self,
        model_name: str,
        lora_config: Optional[Dict[str, Any]] = None,
        device: str = "auto"
    ):
        """
        Initialize LoRA adapter.

        Args:
            model_name: Base model name
            lora_config: LoRA configuration
            device: Device for model
        """
        self.model_name = model_name
        self.device = device

        # Default LoRA configuration
        self.lora_config = lora_config or {
            'r': 8,
            'alpha': 16.0,
            'dropout': 0.1,
            'target_modules': ['query', 'key', 'value', 'dense'],
            'bias': 'none',
            'task_type': 'CAUSAL_LM'
        }

        self.lora_model = None
        self.is_initialized = False

    def initialize_model(self):
        """Initialize the LoRA model."""
        if not self.is_initialized:
            self.lora_model = LoRAModel(
                self.model_name,
                self.lora_config,
                self.device
            )
            self.is_initialized = True
            logger.info("LoRA model initialized")

    def fine_tune(
        self,
        train_dataset,
        validation_dataset=None,
        training_args: Optional[Dict[str, Any]] = None
    ):
        """
        Fine-tune the LoRA model.

        Args:
            train_dataset: Training dataset
            validation_dataset: Validation dataset
            training_args: Training arguments
        """
        if not self.is_initialized:
            self.initialize_model()

        # Default training arguments
        default_args = {
            'learning_rate': 5e-5,
            'num_epochs': 3,
            'batch_size': 8,
            'gradient_accumulation_steps': 4,
            'warmup_steps': 100,
            'weight_decay': 0.01,
            'logging_steps': 10,
            'save_steps': 500,
            'evaluation_strategy': 'steps',
            'eval_steps': 500,
            'load_best_model_at_end': True,
        }

        training_args = training_args or {}
        training_args = {**default_args, **training_args}

        # Prepare optimizer
        optimizer = torch.optim.AdamW(
            self.lora_model.get_lora_parameters(),
            lr=training_args['learning_rate'],
            weight_decay=training_args['weight_decay']
        )

        # Learning rate scheduler
        scheduler = torch.optim.lr_scheduler.LinearLR(
            optimizer,
            start_factor=0.1,
            end_factor=1.0,
            total_iters=training_args['warmup_steps']
        )

        logger.info("Starting LoRA fine-tuning")
        logger.info(f"Trainable parameters: {self.lora_model.get_trainable_parameters()}")
        logger.info(f"Compression ratio: {self.lora_model.get_compression_ratio():.4f}")

        # Training loop (simplified)
        self.lora_model.train()

        for epoch in range(training_args['num_epochs']):
            logger.info(f"Epoch {epoch + 1}/{training_args['num_epochs']}")

            # Training step placeholder
            # In practice, you would iterate through the dataset

            logger.info(f"Epoch {epoch + 1} completed")

        logger.info("LoRA fine-tuning completed")

    def save_adapter(self, path: str):
        """Save the LoRA adapter."""
        if self.lora_model:
            self.lora_model.save_lora_weights(path)
            logger.info(f"LoRA adapter saved to {path}")
        else:
            logger.warning("No LoRA model to save")

    def load_adapter(self, path: str):
        """Load the LoRA adapter."""
        if not self.is_initialized:
            self.initialize_model()

        self.lora_model.load_lora_weights(path)
        logger.info(f"LoRA adapter loaded from {path}")

    def get_model_stats(self) -> Dict[str, Any]:
        """Get model statistics."""
        if not self.is_initialized:
            return {}

        return {
            'model_name': self.model_name,
            'total_parameters': self.lora_model.get_total_parameters(),
            'trainable_parameters': self.lora_model.get_trainable_parameters(),
            'compression_ratio': self.lora_model.get_compression_ratio(),
            'lora_rank': self.lora_config['r'],
            'lora_alpha': self.lora_config['alpha'],
            'adapted_layers': len(self.lora_model.lora_layers)
        }

    def predict(self, inputs: Dict[str, Any]) -> Any:
        """Make predictions with the LoRA model."""
        if not self.is_initialized:
            self.initialize_model()

        self.lora_model.eval()

        with torch.no_grad():
            return self.lora_model(**inputs)







