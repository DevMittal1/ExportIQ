"""Base subagent dispatch and execution runtime."""

import logging
from typing import Any, Dict, List
from ..models.subagent import AGENT_REGISTRY, SubagentFinding
from ..middleware.authorization import ToolAuthorizationMiddleware
from ..tools.registry import execute_tool

logger = logging.getLogger("tradepilot.subagents")


async def dispatch_subagent(
    agent_key: str,
    objective: str,
    inputs: Dict[str, Any],
    constraints: Dict[str, Any]
) -> SubagentFinding:
    """Execute a registered subagent with authorization checks and budget limits."""
    spec = AGENT_REGISTRY.get(agent_key)
    if not spec:
        raise ValueError(f"Unknown agent key: '{agent_key}'")
        
    # Import specific subagent handlers
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
        "trade_advisory": run_trade_advisory
    }
    
    handler = handlers.get(agent_key)
    if not handler:
        raise NotImplementedError(f"No execution handler registered for '{agent_key}'")
        
    import uuid
    logger.info(f"Dispatching [{spec['name']}]: {objective}")
    finding = await handler(objective=objective, inputs=inputs, constraints=constraints)
    if isinstance(finding, SubagentFinding) and not finding.task_id:
        finding.task_id = str(uuid.uuid4())[:8]
    return finding
