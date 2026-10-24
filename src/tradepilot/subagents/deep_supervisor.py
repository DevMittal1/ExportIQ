"""Deep Agent Supervisor for TradePilot using LangChain's deepagents harness.

Provides context-quarantined subagent delegation via the `task` tool,
virtual workspace memory, and deterministic analytical tools.
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from deepagents import create_deep_agent
from langchain_core.messages import BaseMessage

from ..models.state import TradePilotState
from ..models.subagent import AGENT_REGISTRY, SubagentFinding
from ..models.evidence import EvidenceRecord
from ..tools.registry import TOOL_REGISTRY
from .factory import get_model, instrument_tool
from .orchestrator import (
    validate_trade_plan,
    calculate_demand_growth,
    calculate_supplier_concentration,
    build_research_request,
    merge_evidence
)

logger = logging.getLogger("tradepilot.deep_supervisor")

DEEP_SUPERVISOR_SYSTEM_PROMPT = """You are TradePilot's Deep Research Supervisor.
Your mission is to formulate and execute an empirical export feasibility investigation for the user.

You have access to:
1. `task(subagent, task)`: Delegate bounded research investigations to specialized subagents.
   Available subagents:
   - `trade_research`: Product demand trends, import/export flows, historical volumes, market size.
   - `market_access`: Applied MFN tariffs, preferential trade agreements (FTAs), rules of origin, SPS/TBT non-tariff barriers.
   - `buyer_discovery`: Prospective commercial importers, distributor verification, company registration status.
   - `evidence_verification`: Data provenance audit, cross-source statistical variance check, claims verification.
   - `trade_advisory`: Operational Incoterms 2020 rules, trade finance (Letters of Credit, factoring), export logistics.
2. Built-in planning and scratchpad tools (`read_file`, `write_file`, `ls`) for synthesizing complex multi-market intelligence.
3. Deterministic calculation and policy tools:
   - `calculate_demand_growth`: Precise CAGR and volume growth.
   - `calculate_supplier_concentration`: Herfindahl-Hirschman Index (HHI) and CR3 supplier dominance.
   - `validate_trade_plan`: Audit checklist verifying that trade flows, tariffs, and evidence verification are covered.

Operating Protocol:
1. Break down the user inquiry into logical subtasks.
2. Delegate each investigation to the appropriate specialist subagent via `task`.
3. Use deterministic tools for mathematical computations. Never guess growth rates or HHI scores.
4. Ensure `evidence_verification` audits collected empirical records before completing.
5. Provide a clear, comprehensive final synthesized dossier.
"""


def get_deep_subagents(model: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Build the list of specialist subagent definitions for create_deep_agent."""
    subagents = []
    active_model = model or get_model()
    
    for agent_key in ["trade_research", "market_access", "buyer_discovery", "evidence_verification", "trade_advisory"]:
        if agent_key not in AGENT_REGISTRY:
            continue
        cfg = AGENT_REGISTRY[agent_key]
        agent_tools = [
            instrument_tool(tool_name, agent_key=agent_key)
            for tool_name in cfg["tools"]
            if tool_name in TOOL_REGISTRY
        ]
        
        skills_list = cfg.get("skills", [])
        skills_section = (
            f"Available Domain Handbooks: {', '.join(skills_list)}\n"
            "(You can call the 'skills.read_skill' tool if you need detailed procedural guidelines or formulas).\n\n"
            if skills_list else ""
        )
        
        system_prompt = f"""You are {cfg['name']}.
Role: {cfg['description']}
{skills_section}Rules:
- Investigate the assigned task using only your authorized tools.
- Return factual findings, empirical data, exact citations, and limitations.
- Never hallucinate statistics or compliance rules.
"""
        subagents.append({
            "name": agent_key,
            "description": cfg["description"],
            "system_prompt": system_prompt,
            "tools": agent_tools,
            "model": active_model,
            "mode": "isolated"
        })
        
    return subagents


def build_deep_supervisor(model: Optional[Any] = None) -> Any:
    """Build and compile the Deep Agents supervisor state graph."""
    active_model = model or get_model()
    subagents = get_deep_subagents(model=active_model)
    
    tools = [
        validate_trade_plan,
        calculate_demand_growth,
        calculate_supplier_concentration,
    ]
    
    return create_deep_agent(
        model=active_model,
        tools=tools,
        subagents=subagents,
        system_prompt=DEEP_SUPERVISOR_SYSTEM_PROMPT
    )


def extract_deep_findings(result: Any) -> List[Dict[str, Any]]:
    """Extract structured subagent findings from Deep Agent execution messages."""
    findings: List[Dict[str, Any]] = []
    
    if isinstance(result, dict):
        messages = result.get("messages", [])
        for msg in messages:
            tool_name = getattr(msg, "name", None)
            # The Deep Agents delegation tool is named 'task'
            if tool_name == "task":
                content = getattr(msg, "content", None)
                if isinstance(content, str):
                    try:
                        parsed = json.loads(content)
                        if isinstance(parsed, dict) and "agent_name" in parsed:
                            findings.append(parsed)
                            continue
                    except Exception:
                        pass
                    # If returned as raw text or structured string
                    findings.append({
                        "task_id": str(uuid.uuid4())[:8],
                        "agent_name": "DeepSubagent",
                        "objective": "Quarantined delegation",
                        "findings": [content.strip()],
                        "evidence": [],
                        "calculations": {},
                        "limitations": []
                    })
                elif isinstance(content, dict):
                    findings.append(content)
                    
        # Check direct subagent_findings key if populated
        if not findings and "subagent_findings" in result:
            findings = result["subagent_findings"]
            
    return findings


class TradePilotDeepOrchestrator:
    """TradePilot Orchestrator backed by LangChain Deep Agents harness."""
    
    @staticmethod
    def build_supervisor(model: Optional[Any] = None) -> Any:
        return build_deep_supervisor(model)
        
    @staticmethod
    async def run_deep_supervisor(state: TradePilotState, max_iterations: int = 50) -> Dict[str, Any]:
        """Execute dynamic Deep Agent loop with context quarantine and deterministic tools."""
        prompt_content = build_research_request(state)
        agent = build_deep_supervisor()
        
        result = await agent.ainvoke(
            {
                "messages": [{
                    "role": "user",
                    "content": prompt_content
                }]
            },
            config={"recursion_limit": max_iterations}
        )
        extracted = extract_deep_findings(result)
        merged = merge_evidence(extracted)
        return {
            "subagent_findings": extracted,
            "evidence_pool": merged,
            "current_stage": "deep_supervisor_completed"
        }
