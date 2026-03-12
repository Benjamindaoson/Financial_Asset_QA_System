import time
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

class TraceNode:
    def __init__(self, name: str):
        self.name = name
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.children: List[TraceNode] = []
        self.metadata: Dict[str, Any] = {}

    def finish(self):
        self.end_time = time.time()

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return (time.time() - self.start_time) * 1000

class ProfessionalTracer:
    """Simplified professional tracing for AI Agent stages."""
    
    def __init__(self):
        self.root: Optional[TraceNode] = None
        self.current: Optional[TraceNode] = None

    def start_span(self, name: str, metadata: Optional[Dict[str, Any]] = None) -> TraceNode:
        node = TraceNode(name)
        if metadata:
            node.metadata = metadata
        
        if not self.root:
            self.root = node
        
        self.current = node
        return node

    def get_report(self) -> Dict[str, Any]:
        if not self.root:
            return {}
        
        return {
            "trace_id": f"trace_{int(time.time()*1000)}",
            "root_span": self.root.name,
            "total_duration_ms": self.root.duration_ms,
            "timestamp": datetime.utcnow().isoformat(),
        }

# Global tracer instance
tracer = ProfessionalTracer()
