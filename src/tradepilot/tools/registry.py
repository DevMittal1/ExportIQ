"""Agent-facing tool registry, decorator, and execution dispatcher."""

from typing import Any, Callable, Dict, List, Optional
import inspect
from pydantic import BaseModel, ConfigDict


class ToolDefinition(BaseModel):
    """Metadata and execution interface for an agent-facing business tool."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    input_schema: Dict[str, Any]
    function: Any


TOOL_REGISTRY: Dict[str, ToolDefinition] = {}


def register_tool(name: str, description: str, input_schema: Dict[str, Any]):
    """Decorator to register an agent-facing tool in the global TOOL_REGISTRY."""
    def decorator(fn: Callable):
        TOOL_REGISTRY[name] = ToolDefinition(
            name=name,
            description=description,
            input_schema=input_schema,
            function=fn
        )
        return fn
    return decorator


async def execute_tool(tool_name: str, **kwargs) -> Any:
    """Execute a registered tool by canonical name."""
    if tool_name not in TOOL_REGISTRY:
        raise ValueError(f"Tool '{tool_name}' not found in TOOL_REGISTRY. Available: {list(TOOL_REGISTRY.keys())}")
    
    tool = TOOL_REGISTRY[tool_name]
    fn = tool.function
    if inspect.iscoroutinefunction(fn):
        return await fn(**kwargs)
    return fn(**kwargs)
