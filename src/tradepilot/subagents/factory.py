"""Subagent factory and tool instrumentation for TradePilot AI specialists."""

import os
import asyncio
from typing import Any, Callable, Dict, List, Optional
from langchain_core.tools import StructuredTool
from langchain.agents import create_agent
from dotenv import load_dotenv

from ..models.subagent import AGENT_REGISTRY
from ..tools.registry import TOOL_REGISTRY, execute_tool

load_dotenv()


def instrument_tool(
    tool_name: str,
    agent_key: str,
    budget_tracker: Optional[Dict[str, int]] = None
) -> StructuredTool:
    """Wrap a tool from TOOL_REGISTRY with authorization, budget enforcement, and telemetry."""
    if tool_name not in TOOL_REGISTRY:
        raise ValueError(f"Tool '{tool_name}' not found in TOOL_REGISTRY")
    
    tool_def = TOOL_REGISTRY[tool_name]
    
    import functools
    import inspect

    tool_sig = inspect.signature(tool_def.function)

    async def _async_exec(*args, **kwargs) -> Any:
        if budget_tracker is not None:
            max_calls = budget_tracker.get("max_calls", 10)
            current_calls = budget_tracker.get("current_calls", 0)
            if current_calls >= max_calls:
                raise RuntimeError(
                    f"Dispatch tool budget exceeded: {agent_key} reached limit of {max_calls} calls."
                )
            budget_tracker["current_calls"] = current_calls + 1
            
        return await execute_tool(tool_name, agent_name=agent_key, *args, **kwargs)

    functools.update_wrapper(_async_exec, tool_def.function)
    _async_exec.__signature__ = tool_sig

    def _sync_exec(*args, **kwargs) -> Any:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, _async_exec(*args, **kwargs)).result()
        return asyncio.run(_async_exec(*args, **kwargs))

    functools.update_wrapper(_sync_exec, tool_def.function)
    _sync_exec.__signature__ = tool_sig

    return StructuredTool.from_function(
        func=_sync_exec,
        coroutine=_async_exec,
        name=tool_def.name.replace(".", "_"),
        description=tool_def.description
    )


def get_model(temperature: float = 0.1) -> Any:
    """Instantiate primary Chat LLM or mock fallback."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    model_name = os.getenv("PRIMARY_MODEL", "gemini-3.8-flash")
    
    if api_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=model_name,
                api_key=api_key,
                temperature=temperature
            )
        except Exception:
            pass
            
    # Mock fallback for test isolation
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langchain_core.messages import AIMessage
    return GenericFakeChatModel(
        messages=iter([AIMessage(content="Task executed successfully with empirical evidence.")])
    )


def build_subagent(agent_key: str, model: Optional[Any] = None) -> Any:
    """Build a specialist ReAct agent using create_agent and instrumented tools."""
    if agent_key not in AGENT_REGISTRY:
        raise ValueError(f"Unknown agent key: '{agent_key}'")
        
    config = AGENT_REGISTRY[agent_key]
    agent_tools = [
        instrument_tool(tool_name, agent_key=agent_key)
        for tool_name in config["tools"]
        if tool_name in TOOL_REGISTRY
    ]
    
    skills_list = config.get("skills", [])
    skills_section = (
        f"Available Domain Handbooks: {', '.join(skills_list)}\n"
        "(You can call the 'skills.read_skill' tool if you need detailed procedural guidelines or formulas).\n"
        if skills_list else ""
    )
    
    system_prompt = f"""You are {config['name']}.
Mission: {config['description']}
{skills_section}Rules:
- Investigate the assigned objective using only your authorized tools.
- Return factual findings, empirical evidence, deterministic calculations, and limitations.
- Never invent or fabricate missing evidence.
- State any data gaps or follow-up recommendations explicitly.
"""
    
    active_model = model or get_model()
    return create_agent(
        model=active_model,
        tools=agent_tools,
        system_prompt=system_prompt
    )


class _SubagentRegistry(dict):
    """Lazy dictionary of compiled subagents."""
    def __missing__(self, key: str):
        if key in AGENT_REGISTRY:
            agent = build_subagent(key)
            self[key] = agent
            return agent
        raise KeyError(f"Specialist '{key}' not registered in AGENT_REGISTRY")


SUBAGENTS: Dict[str, Any] = _SubagentRegistry()
