"""TradePilot ReAct Supervisor and LLM-driven specialist orchestration."""

import json
import logging
from typing import Any, Dict, List, Optional
from langchain_core.tools import StructuredTool
from deepagents import create_deep_agent

from ..models.state import TradePilotState
from ..models.subagent import AGENT_REGISTRY, SubagentFinding
from ..tools.registry import execute_tool
from .factory import get_model
from .dispatch import dispatch_subagent, SPECIALIST_TOOLS

logger = logging.getLogger("tradepilot.supervisor")


# --- Deterministic Calculation & Validation Tools for Supervisor ---

def _validate_trade_plan_sync(destinations: List[str], completed_agents: List[str]) -> Dict[str, Any]:
    """Validate whether mandatory investigation domains and compliance checks have been covered."""
    missing = []
    if destinations:
        if "trade_research" not in completed_agents and "TradeResearchAgent" not in completed_agents:
            missing.append("trade_research")
        if "market_access" not in completed_agents and "MarketAccessAgent" not in completed_agents:
            missing.append("market_access")
    if "evidence_verification" not in completed_agents and "EvidenceVerificationAgent" not in completed_agents:
        missing.append("evidence_verification")
        
    return {
        "valid": len(missing) == 0,
        "missing_investigations": missing,
        "completed_count": len(completed_agents),
        "status": "ready_for_scoring" if not missing else "additional_dispatches_needed"
    }


async def _validate_trade_plan_async(destinations: List[str], completed_agents: List[str]) -> Dict[str, Any]:
    return _validate_trade_plan_sync(destinations, completed_agents)


validate_trade_plan = StructuredTool.from_function(
    func=_validate_trade_plan_sync,
    coroutine=_validate_trade_plan_async,
    name="validate_trade_plan",
    description="Deterministic validator to verify whether all required research areas (trade flows, tariffs, and evidence verification) have been audited."
)


def _calc_demand_growth_sync(observations: List[Dict[str, Any]]) -> Dict[str, Any]:
    import asyncio
    return asyncio.run(execute_tool("analytics.calculate_demand_growth", observations=observations))


async def _calc_demand_growth_async(observations: List[Dict[str, Any]]) -> Dict[str, Any]:
    return await execute_tool("analytics.calculate_demand_growth", observations=observations)


calculate_demand_growth = StructuredTool.from_function(
    func=_calc_demand_growth_sync,
    coroutine=_calc_demand_growth_async,
    name="calculate_demand_growth",
    description="Calculate compound annual growth rate (CAGR), absolute growth, and volume trends from historical trade observations."
)


def _calc_supplier_conc_sync(partner_values: Dict[str, float]) -> Dict[str, Any]:
    import asyncio
    return asyncio.run(execute_tool("analytics.calculate_supplier_concentration", partner_values=partner_values))


async def _calc_supplier_conc_async(partner_values: Dict[str, float]) -> Dict[str, Any]:
    return await execute_tool("analytics.calculate_supplier_concentration", partner_values=partner_values)


calculate_supplier_concentration = StructuredTool.from_function(
    func=_calc_supplier_conc_sync,
    coroutine=_calc_supplier_conc_async,
    name="calculate_supplier_concentration",
    description="Calculate Herfindahl-Hirschman Index (HHI) and market competition concentration category from supplier trade shares."
)


# --- Prompt & Helper Functions ---

SUPERVISOR_SYSTEM_PROMPT = """You are TradePilot's ReAct supervisor.
Your job is to answer the user's trade research question using specialist agents backed by a shared dispatch layer.
You have five specialist tools:
- trade_research(objective, inputs): market demand, trade flows, import CAGR, supplier concentration
- market_access(objective, inputs): tariffs, preferential trade rates, rules of origin, compliance and NTBs
- buyer_discovery(objective, inputs): prospective commercial importers, distributors, buyer verification
- evidence_verification(objective, inputs): source validation and conflicting claims audit
- trade_advisory(objective, inputs): export documentation, logistics, Incoterms, and trade finance

Operating rules:
1. Identify what information is required to answer the question.
2. Delegate specific, bounded tasks to the appropriate specialists.
3. Review returned findings before deciding what to do next.
4. You may call the same specialist multiple times with refined inputs.
5. You may call different specialists in any appropriate sequence.
6. Use findings from previous calls to formulate follow-up tasks.
7. Investigate material evidence gaps and contradictions before concluding.
8. Do not invent trade statistics, buyers, tariffs or citations.
9. Do not perform arithmetic that should use deterministic calculation tools (CAGR, HHI).
10. Stop when the required evidence is sufficient, or the budget is exhausted.
11. Report unresolved gaps and uncertainty honestly.
12. Never bypass application-enforced permissions or research limits.
"""


def build_research_request(state: TradePilotState) -> str:
    """Format structured state into actionable prompt for the ReAct supervisor."""
    query = state.get("query") or ""
    product = state.get("product_query")
    origin = state.get("origin_country")
    destinations = state.get("candidate_destinations") or []
    hs_code = state.get("hs_code")
    intent = state.get("query_intent")
    years = state.get("reference_years") or [2021, 2022, 2023]
    
    query_lower = query.lower()
    market_keywords = [
        "best market", "which country", "where can i export", "where should i export",
        "recommend market", "top market", "top importer", "candidate market",
        "feasibility", "target destination", "target market", "market prioritize"
    ]
    has_market_intent = any(k in query_lower for k in market_keywords)
    
    if not intent:
        if product and (destinations or has_market_intent or "export" in query_lower):
            intent = "comprehensive_feasibility"
        elif not product and not destinations and not has_market_intent:
            intent = "trade_advisory"
        else:
            intent = "comprehensive_feasibility"
            
    product_str = product or ("General Trade Advisory" if intent == "trade_advisory" else "Extract product entity from inquiry")
    origin_str = origin if origin else "Extract from inquiry (or deduce if specified)"
    hs_str = hs_code if hs_code else ("N/A" if intent == "trade_advisory" else "Deduce 6-digit HS code from product if applicable")
    
    if intent == "trade_advisory":
        instructions = (
            "This is a trade advisory or informational inquiry. Answer the user's inquiry directly, thoroughly, and concisely. "
            "Dispatch trade_advisory or relevant tools if specific trade regulations, Incoterms, procedures, or metrics are needed. "
            "Do not auto-discover target destinations or generate market ranking tables unless explicitly requested."
        )
    else:
        instructions = (
            "Formulate your dynamic investigation plan using your specialist tools. "
            "If investigating destinations, evaluate trade flows, tariffs, and potential buyers. "
            "Always conclude by verifying evidence with evidence_verification."
        )
    
    return (
        f"Research Request:\n"
        f"- Inquiry: {query or product_str}\n"
        f"- Product: {product_str}\n"
        f"- Reference HS Code: {hs_str}\n"
        f"- Exporter Origin: {origin_str}\n"
        f"- Candidate Destinations: {destinations if destinations else ('None' if intent == 'trade_advisory' else 'Auto-discover appropriate target markets')}\n"
        f"- Historical Periods: {years}\n"
        f"- Query Intent: {intent}\n\n"
        f"Instructions:\n{instructions}"
    )


SPECIALIST_TOOL_NAMES = {
    "dispatch_subagent",
    "trade_research",
    "market_access",
    "buyer_discovery",
    "evidence_verification",
    "trade_advisory",
}


def extract_findings(result: Any) -> List[Dict[str, Any]]:
    """Extract structured subagent findings from agent execution observations."""
    findings: List[Dict[str, Any]] = []
    
    if isinstance(result, dict):
        messages = result.get("messages", [])
        for msg in messages:
            # Check for tool call outputs from specialist tools or dispatch_subagent
            tool_name = getattr(msg, "name", None)
            if tool_name in SPECIALIST_TOOL_NAMES:
                content = getattr(msg, "content", None)
                if isinstance(content, str):
                    try:
                        parsed = json.loads(content)
                        if isinstance(parsed, dict) and "agent_name" in parsed:
                            findings.append(parsed)
                    except Exception:
                        pass
                elif isinstance(content, dict) and "agent_name" in content:
                    findings.append(content)
                    
        # Check direct subagent_findings key if populated
        if not findings and "subagent_findings" in result:
            findings = result["subagent_findings"]
            
    return findings


def merge_evidence(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate and aggregate evidence records across all specialist findings."""
    evidence_pool: List[Dict[str, Any]] = []
    seen_ids = set()
    
    for f in findings:
        for ev in f.get("evidence", []):
            ev_dict = ev if isinstance(ev, dict) else ev.model_dump()
            ev_id = ev_dict.get("evidence_id")
            if ev_id and ev_id not in seen_ids:
                seen_ids.add(ev_id)
                evidence_pool.append(ev_dict)
            elif not ev_id:
                evidence_pool.append(ev_dict)
                
    return evidence_pool


def build_supervisor(model: Optional[Any] = None) -> Any:
    """Build the compiled Deep Agents supervisor harness with 5 specialist tools and deterministic tools."""
    tools = [
        *SPECIALIST_TOOLS,
        validate_trade_plan,
        calculate_demand_growth,
        calculate_supplier_concentration,
    ]
    active_model = model or get_model()
    return create_deep_agent(
        model=active_model,
        tools=tools,
        system_prompt=SUPERVISOR_SYSTEM_PROMPT
    )


class _SupervisorProxy:
    """Supervisor proxy ensuring fresh event-loop binding per execution."""
    def get(self):
        return build_supervisor()

    async def ainvoke(self, *args, **kwargs):
        return await self.get().ainvoke(*args, **kwargs)

    def invoke(self, *args, **kwargs):
        return self.get().invoke(*args, **kwargs)


supervisor = _SupervisorProxy()


# --- TradePilotOrchestrator ReAct Supervisor Runtime ---

class TradePilotOrchestrator:
    """LLM-driven ReAct Supervisor coordinating specialist agents at runtime."""
    
    @staticmethod
    def build_supervisor(model: Optional[Any] = None) -> Any:
        return build_supervisor(model)
        
    @staticmethod
    async def run_react_supervisor(state: TradePilotState, max_iterations: int = 50) -> Dict[str, Any]:
        """Execute dynamic ReAct supervisor loop with observation-driven specialist dispatch."""
        prompt_content = build_research_request(state)
        
        result = await supervisor.ainvoke(
            {
                "messages": [{
                    "role": "user",
                    "content": prompt_content
                }]
            },
            config={"recursion_limit": max_iterations}
        )
        extracted = extract_findings(result)
        merged = merge_evidence(extracted)
        
        # Extract direct supervisor synthesized response
        direct_answer = None
        messages = result.get("messages", []) if isinstance(result, dict) else []
        if messages:
            last_msg = messages[-1]
            content = getattr(last_msg, "content", None) or (last_msg.get("content") if isinstance(last_msg, dict) else None)
            if isinstance(content, list):
                content = "\n".join(
                    b.get("text", "") if isinstance(b, dict) else str(b)
                    for b in content
                    if not (isinstance(b, dict) and b.get("type") != "text")
                )
            if content and isinstance(content, str) and content.strip():
                direct_answer = content.strip()

        return {
            "direct_answer": direct_answer,
            "subagent_findings": extracted,
            "evidence_pool": merged,
            "current_stage": "supervisor_completed"
        }
