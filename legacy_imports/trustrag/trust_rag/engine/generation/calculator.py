"""
Deterministic Sandbox Calculator for Financial Queries.
Provides safe operations without LLM hallucinations.
"""
import logging
from typing import List, Dict, Any, Optional
import ast
import operator

logger = logging.getLogger(__name__)

class DeterministicCalculator:
    """Safe, isolated calculator for exact financial arithmetic."""
    
    def __init__(self):
        # White-listed operations for safety
        self.operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.USub: operator.neg,
        }
        
    def _eval_node(self, node):
        """Recursively evaluate an AST node safely."""
        if isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.BinOp):
            return self.operators[type(node.op)](
                self._eval_node(node.left), self._eval_node(node.right)
            )
        elif isinstance(node, ast.UnaryOp):
            return self.operators[type(node.op)](self._eval_node(node.operand))
        else:
            raise TypeError(f"Unsupported mathematical operation: {node}")

    def safe_eval(self, expression: str) -> Optional[float]:
        """Evaluate a mathematical expression safely."""
        try:
            # Simple sanitization
            expression = expression.replace(',', '').replace('$', '').replace('%', '')
            node = ast.parse(expression, mode='eval').body
            result = self._eval_node(node)
            logger.info(f"Sandbox Calculator evaluated: {expression} -> {result}")
            return result
        except Exception as e:
            logger.warning(f"Failed to cleanly evaluate expression {expression}: {e}")
            return None
            
    def calculate_growth_rate(self, current: float, previous: float) -> Optional[float]:
        """Calculate YoY/QoQ growth rate perfectly."""
        if previous == 0:
            return None
        return ((current - previous) / previous) * 100
