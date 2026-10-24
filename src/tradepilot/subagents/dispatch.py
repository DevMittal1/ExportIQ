"""Specialist subagent dispatch tool and bounded invocation choke-point."""

import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional
from langchain_core.tools import StructuredTool

from ..models.subagent import AGENT_REGISTRY, SubagentFinding
from ..models.evidence import EvidenceRecord
from .factory import SUBAGENTS

logger = logging.getLogger("tradepilot.dispatch")


def normalize_finding(
    result: Any,
    agent_name: str,
    task_id: str,
    objective: str
) -> Dict[str, Any]:
    """Validate specialist outcome and normalize into standardized SubagentFinding structure."""
    if isinstance(result, SubagentFinding):
        data = result.model_dump()
        data["task_id"] = task_id or data.get("task_id") or str(uuid.uuid4())[:8]
        return data

    if isinstance(result, dict):
        if "agent_name" in result and "findings" in result:
            result["task_id"] = task_id or result.get("task_id") or str(uuid.uuid4())[:8]
            return result
        
        # If result is from LangChain agent state graph with messages
        messages = result.get("messages", [])
        findings: List[str] = []
        evidence_list: List[Dict[str, Any]] = []
        calculations: Dict[str, Any] = {}
        limitations: List[str] = []
        
        for msg in messages:
            content = getattr(msg, "content", "")
            if isinstance(content, str) and content.strip():
                findings.append(content.strip())
                
        return SubagentFinding(
            task_id=task_id or str(uuid.uuid4())[:8],
            agent_name=AGENT_REGISTRY.get(agent_name, {}).get("name", agent_name),
            objective=objective,
            findings=findings or [f"Investigation completed for {objective}"],
            evidence=[EvidenceRecord(**e) for e in evidence_list],
            calculations=calculations,
            limitations=limitations,
            follow_up_tasks=[]
        ).model_dump()

    return SubagentFinding(
        task_id=task_id or str(uuid.uuid4())[:8],
        agent_name=AGENT_REGISTRY.get(agent_name, {}).get("name", agent_name),
        objective=objective,
        findings=[str(result)],
        evidence=[],
        calculations={},
        limitations=[],
        follow_up_tasks=[]
    ).model_dump()


async def invoke_bounded(
    agent: Any,
    agent_name: str,
    task_id: str,
    objective: str,
    inputs: Dict[str, Any],
    max_tool_calls: int = 10,
    timeout_seconds: int = 60,
    request_budget_tracker: Optional[Dict[str, int]] = None
) -> Any:
    """Execute specialist with strict application-enforced quota and timeout limits."""
    config = AGENT_REGISTRY[agent_name]
    
    # Application-enforced limits, not model-controlled limits
    enforced_max_calls = min(max_tool_calls, config.get("max_tool_calls", 10))
    enforced_timeout = min(timeout_seconds, config.get("timeout_seconds", 60))
    
    # Check request-level budget if provided
    if request_budget_tracker:
        total_spent = request_budget_tracker.get("total_calls", 0)
        request_limit = request_budget_tracker.get("max_calls", 50)
        if total_spent >= request_limit:
            raise RuntimeError(f"Request-level budget exceeded: {total_spent}/{request_limit} tool calls used.")

    # Handlers for specialized domain execution
    from .trade_research import run_trade_research
    from .market_access import run_market_access
    from .buyer_discovery import run_buyer_discovery
    from .evidence_verification import run_evidence_verification
    from .trade_advisory import run_trade_advisory

    handlers = {
        "trade_research": run_trade_research,
        "market_access": run_market_access,
        "buyer_discovery": run_buyer_discovery,
        "evidence_verification": run_evidence_verification,
        "trade_advisory": run_trade_advisory,
    }

    handler = handlers.get(agent_name)
    if not handler:
        raise ValueError(f"No execution handler registered for specialist '{agent_name}'")

    logger.info(f"invoke_bounded [{agent_name}] task_id={task_id} timeout={enforced_timeout}s")
    
    # Execute within timeout bound
    return await asyncio.wait_for(
        handler(
            objective=objective,
            inputs=inputs or {},
            constraints={"max_tool_calls": enforced_max_calls}
        ),
        timeout=float(enforced_timeout)
    )


async def _async_dispatch_subagent(
    agent_name: str,
    objective: str,
    inputs: Optional[Dict[str, Any]] = None,
    task_id: str = ""
) -> Dict[str, Any]:
    """Run a registered TradePilot specialist on a bounded task."""
    if agent_name not in AGENT_REGISTRY:
        raise ValueError(f"Unknown specialist '{agent_name}'. Available: {list(AGENT_REGISTRY.keys())}")
        
    config = AGENT_REGISTRY[agent_name]
    active_task_id = task_id or str(uuid.uuid4())[:8]
    active_inputs = inputs or {}
    
    result = await invoke_bounded(
        agent=SUBAGENTS[agent_name],
        agent_name=agent_name,
        task_id=active_task_id,
        objective=objective,
        inputs=active_inputs,
        max_tool_calls=config["max_tool_calls"],
        timeout_seconds=config["timeout_seconds"],
    )
    
    return normalize_finding(
        result=result,
        agent_name=agent_name,
        task_id=active_task_id,
        objective=objective,
    )


def _sync_dispatch_subagent(
    agent_name: str,
    objective: str,
    inputs: Optional[Dict[str, Any]] = None,
    task_id: str = ""
) -> Dict[str, Any]:
    """Synchronous bridge for dispatch_subagent."""
    return asyncio.run(_async_dispatch_subagent(
        agent_name=agent_name,
        objective=objective,
        inputs=inputs,
        task_id=task_id
    ))


dispatch_subagent = StructuredTool.from_function(
    func=_sync_dispatch_subagent,
    coroutine=_async_dispatch_subagent,
    name="dispatch_subagent",
    description="Run a registered TradePilot specialist agent on a bounded task (e.g. trade_research, market_access, buyer_discovery, evidence_verification, trade_advisory)."
)


def make_specialist_tool(agent_name: str, description: Optional[str] = None) -> StructuredTool:
    """Create a dedicated supervisor tool for a specialist backed by the shared dispatch layer."""
    config = AGENT_REGISTRY.get(agent_name, {})
    desc = description or config.get("description", f"Dispatch task to {agent_name} specialist.")
    
    async def _specialist_coro(
        objective: str,
        inputs: Optional[Dict[str, Any]] = None,
        task_id: str = ""
    ) -> Dict[str, Any]:
        """Dispatch one bounded research task to this specialist."""
        return await _async_dispatch_subagent(
            agent_name=agent_name,
            objective=objective,
            inputs=inputs or {},
            task_id=task_id
        )
        
    def _specialist_sync(
        objective: str,
        inputs: Optional[Dict[str, Any]] = None,
        task_id: str = ""
    ) -> Dict[str, Any]:
        return asyncio.run(_specialist_coro(objective, inputs, task_id))
        
    return StructuredTool.from_function(
        func=_specialist_sync,
        coroutine=_specialist_coro,
        name=agent_name,
        description=desc
    )


trade_research_tool = make_specialist_tool(
    "trade_research",
    "Investigate market demand, trade flows, import CAGR, and supplier concentration."
)
market_access_tool = make_specialist_tool(
    "market_access",
    "Investigate tariffs, preferential trade rates, rules of origin, and compliance."
)
buyer_discovery_tool = make_specialist_tool(
    "buyer_discovery",
    "Identify verified prospective commercial importers, distributors, and buyers."
)
evidence_verification_tool = make_specialist_tool(
    "evidence_verification",
    "Audit evidence records, detect cross-source statistical variance, and verify claims."
)
trade_advisory_tool = make_specialist_tool(
    "trade_advisory",
    "Advise on Incoterms, trade finance, export licensing, and documentation procedures."
)

SPECIALIST_TOOLS = [
    trade_research_tool,
    market_access_tool,
    buyer_discovery_tool,
    evidence_verification_tool,
    trade_advisory_tool,
]

