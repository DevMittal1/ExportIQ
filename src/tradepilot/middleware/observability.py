"""Observability, telemetry, and execution metrics middleware."""

import time
from typing import Any, Dict, List


class ObservabilityMiddleware:
    """Tracks latency, step counts, tool calls, and execution metadata."""
    
    def __init__(self):
        self.spans: List[Dict[str, Any]] = []
        self.tool_call_count: int = 0
        self.start_time: float = time.time()
        
    def record_tool_call(self, tool_name: str, duration_seconds: float, status: str = "success"):
        """Record tool execution telemetry."""
        self.tool_call_count += 1
        self.spans.append({
            "type": "tool_call",
            "name": tool_name,
            "duration": round(duration_seconds, 3),
            "status": status,
            "timestamp": time.time()
        })
        
    def get_summary(self) -> Dict[str, Any]:
        """Generate execution summary report."""
        total_duration = time.time() - self.start_time
        return {
            "total_execution_seconds": round(total_duration, 2),
            "total_tool_calls": self.tool_call_count,
            "spans_recorded": len(self.spans)
        }
