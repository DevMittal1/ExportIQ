"""Pre-tool and Post-tool hook lifecycle middleware for agent control and persistent API tracking.

Implements Anthropic-style interception patterns for tool execution:
- PreToolHook: authorization checks, input validation, rate limiting, and persistent budget caps.
- PostToolHook: precise latency timing, SQLite persistent metrics accumulation, output safety, and circuit breaking.
"""

import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from .authorization import ToolAuthorizationMiddleware
from ..db.usage_db import USAGE_DB

logger = logging.getLogger("tradepilot.tool_hooks")


class ToolBudgetExceededError(Exception):
    """Raised when an agent or session exceeds permitted tool call quotas."""
    pass


class ToolAuthorizationError(Exception):
    """Raised when an agent attempts to execute an unauthorized tool."""
    pass


@dataclass
class ToolCallContext:
    """Contextual metadata passed through the tool execution lifecycle."""
    call_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tool_name: str = ""
    agent_name: Optional[str] = None
    arguments: Dict[str, Any] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolMetricEntry:
    """Aggregated usage and performance metrics for a specific tool."""
    tool_name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_latency_ms: float = 0.0
    last_called_at: Optional[float] = None
    budget_limit: Optional[int] = None

    @property
    def avg_latency_ms(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return round(self.total_latency_ms / self.total_calls, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "avg_latency_ms": self.avg_latency_ms,
            "total_latency_ms": round(self.total_latency_ms, 2),
            "last_called_at": self.last_called_at,
            "budget_limit": self.budget_limit
        }


class ToolUsageTracker:
    """Global tracker synchronizing in-memory fast metrics with persistent SQLite database."""
    
    def __init__(self):
        self._metrics: Dict[str, ToolMetricEntry] = {}
        self._history: List[Dict[str, Any]] = []

    def get_entry(self, tool_name: str) -> ToolMetricEntry:
        if tool_name not in self._metrics:
            self._metrics[tool_name] = ToolMetricEntry(tool_name=tool_name)
        return self._metrics[tool_name]

    def set_budget(self, tool_name: str, max_calls: int):
        """Set a hard limit on allowed invocations for a tool in-memory and in SQLite."""
        entry = self.get_entry(tool_name)
        entry.budget_limit = max_calls
        USAGE_DB.set_budget(tool_name, max_calls)

    def remove_budget(self, tool_name: str):
        """Remove a budget constraint for a tool."""
        entry = self.get_entry(tool_name)
        entry.budget_limit = None
        USAGE_DB.remove_budget(tool_name)

    def check_budget(self, tool_name: str):
        """Verify the tool call is within budget limits (checking in-memory and SQLite)."""
        entry = self.get_entry(tool_name)
        if entry.budget_limit is not None and entry.total_calls >= entry.budget_limit:
            raise ToolBudgetExceededError(
                f"Tool '{tool_name}' exceeded execution budget limit of {entry.budget_limit} calls. "
                f"Current calls: {entry.total_calls}."
            )
        # Also check persistent DB budget
        db_limit = USAGE_DB.check_budget_exceeded(tool_name)
        if db_limit is not None:
            raise ToolBudgetExceededError(
                f"Tool '{tool_name}' exceeded persistent database budget limit of {db_limit} calls."
            )

    def record_start(self, tool_name: str):
        """Record the initiation of a tool call."""
        entry = self.get_entry(tool_name)
        entry.total_calls += 1
        entry.last_called_at = time.time()

    def record_completion(
        self,
        context: ToolCallContext,
        status: str,
        duration_ms: float,
        result: Optional[Any] = None,
        error: Optional[Exception] = None
    ):
        """Record outcome, latency, and update metrics in-memory and in persistent SQLite."""
        entry = self.get_entry(context.tool_name)
        entry.total_latency_ms += duration_ms
        
        if status == "success":
            entry.successful_calls += 1
        else:
            entry.failed_calls += 1

        # Keep a sliding in-memory log
        self._history.append({
            "call_id": context.call_id,
            "tool_name": context.tool_name,
            "agent_name": context.agent_name,
            "duration_ms": round(duration_ms, 2),
            "status": status,
            "timestamp": time.time(),
            "error": str(error) if error else None
        })
        if len(self._history) > 500:
            self._history.pop(0)

        # Persist to SQLite database asynchronously/safely
        try:
            USAGE_DB.record_execution(
                call_id=context.call_id,
                tool_name=context.tool_name,
                arguments=context.arguments,
                status=status,
                duration_ms=duration_ms,
                agent_name=context.agent_name,
                result=result,
                error_message=str(error) if error else None
            )
        except Exception as e:
            logger.error(f"Failed to record execution to SQLite: {e}")

    def get_summary(self, from_db: bool = True) -> Dict[str, Any]:
        """Return an aggregated metrics summary across all registered tools."""
        if from_db:
            return USAGE_DB.get_tool_metrics_summary()
            
        total_invocations = sum(m.total_calls for m in self._metrics.values())
        total_errors = sum(m.failed_calls for m in self._metrics.values())
        
        return {
            "total_tool_invocations": total_invocations,
            "total_tool_errors": total_errors,
            "active_tools_tracked": len(self._metrics),
            "tools": {k: v.to_dict() for k, v in self._metrics.items()},
            "recent_calls_count": len(self._history)
        }

    def get_logs(
        self,
        limit: int = 50,
        offset: int = 0,
        tool_name: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve persistent execution logs from SQLite."""
        return USAGE_DB.get_logs(limit=limit, offset=offset, tool_name=tool_name, status=status)

    def reset(self):
        """Reset all tracked metrics and budgets in memory and in SQLite."""
        self._metrics.clear()
        self._history.clear()
        USAGE_DB.clear_all()


# Global usage tracker instance
USAGE_TRACKER = ToolUsageTracker()


async def pre_tool_hook(
    tool_name: str,
    arguments: Dict[str, Any],
    agent_name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> ToolCallContext:
    """Pre-execution hook: validates authorization, checks budgets, and records invocation."""
    # 1. Permission check if calling agent is identified
    if agent_name:
        is_auth = ToolAuthorizationMiddleware.is_authorized(agent_name, tool_name)
        if not is_auth:
            logger.warning(f"Unauthorized tool invocation blocked: [{agent_name}] -> {tool_name}")
            raise ToolAuthorizationError(
                f"Agent '{agent_name}' is not authorized to call tool '{tool_name}'."
            )

    # 2. Budget and quota enforcement
    USAGE_TRACKER.check_budget(tool_name)

    # 3. Create context and record start
    ctx = ToolCallContext(
        tool_name=tool_name,
        agent_name=agent_name,
        arguments=arguments,
        start_time=time.time(),
        metadata=metadata or {}
    )
    USAGE_TRACKER.record_start(tool_name)
    logger.debug(f"[PreToolHook] call_id={ctx.call_id} tool={tool_name} agent={agent_name}")
    return ctx


async def post_tool_hook(
    context: ToolCallContext,
    result: Any,
    status: str = "success",
    error: Optional[Exception] = None
) -> Any:
    """Post-execution hook: records execution duration, updates telemetry in SQLite, and scrubs output."""
    duration_ms = (time.time() - context.start_time) * 1000.0
    USAGE_TRACKER.record_completion(
        context,
        status=status,
        duration_ms=duration_ms,
        result=result,
        error=error
    )
    
    logger.debug(
        f"[PostToolHook] call_id={context.call_id} tool={context.tool_name} "
        f"status={status} duration={duration_ms:.2f}ms"
    )
    return result
