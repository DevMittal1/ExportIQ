"""Agent-facing tool registry, decorator, and execution dispatcher with hook interception."""

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


async def execute_tool(tool_name: str, agent_name: Optional[str] = None, **kwargs) -> Any:
    """Execute a registered tool by canonical name through pre/post execution hooks."""
    if tool_name not in TOOL_REGISTRY:
        raise ValueError(f"Tool '{tool_name}' not found in TOOL_REGISTRY. Available: {list(TOOL_REGISTRY.keys())}")
    
    # Lazy import to prevent circular dependencies
    from ..middleware.tool_hooks import pre_tool_hook, post_tool_hook
    
    # 1. Pre-execution Hook (authorization, budget check, start timing)
    context = await pre_tool_hook(tool_name=tool_name, arguments=kwargs, agent_name=agent_name)
    
    tool = TOOL_REGISTRY[tool_name]
    fn = tool.function
    
    try:
        # 2. Tool Execution
        if inspect.iscoroutinefunction(fn):
            result = await fn(**kwargs)
        else:
            result = fn(**kwargs)
            
        # 3. Post-execution Hook (latency timing, metrics tracking, output validation)
        return await post_tool_hook(context=context, result=result, status="success")
    except Exception as exc:
        await post_tool_hook(context=context, result=None, status="error", error=exc)
        raise exc
