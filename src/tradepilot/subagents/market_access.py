"""MarketAccessAgent implementation with parallel tool execution."""

import asyncio
from typing import Any, Dict, List
from ..models.subagent import SubagentFinding
from ..models.evidence import EvidenceRecord
from ..tools.registry import execute_tool


async def _evaluate_destination_market_access(
    dest: str,
    hs_code: str,
    origin: str
) -> Dict[str, Any]:
    """Execute MFN tariff, preferential agreement, and SPS/TBT tool checks concurrently in parallel."""
    # Execute all 3 independent tools concurrently
    tariff_task = execute_tool(
        "tariffs.get_applied_rate",
        hs_code=hs_code,
        origin=origin,
        destination=dest
    )
    pref_task = execute_tool(
        "tariffs.check_preferential_rate",
        hs_code=hs_code,
        origin=origin,
        destination=dest
    )
    comp_task = execute_tool(
        "compliance.search_product_requirements",
        hs_code=hs_code,
        origin=origin,
        destination=dest
    )
    
    tariff_res, pref_res, comp_res = await asyncio.gather(tariff_task, pref_task, comp_task)
    
    applied_rate = tariff_res.get("applied_rate_percent", 0.0)
    evidence_records = [EvidenceRecord(**r) for r in tariff_res.get("evidence_records", [])]
    
    reqs = comp_res.get("requirements", [])
    req_count = len(reqs)
    
    pref_text = (
        f"Preferential rate under {pref_res.get('agreement_name')} is {pref_res.get('preferential_rate')}"
        if pref_res.get("is_preferential_available")
        else "No preferential trade agreement active"
    )
    
    finding = (
        f"Market access for {dest}: Standard MFN tariff is {applied_rate}%. {pref_text}. "
        f"Identified {req_count} key regulatory compliance measures."
    )
    
    tariff_details = {
        "applied_mfn": applied_rate,
        "preferential_available": pref_res.get("is_preferential_available", False),
        "requirements_count": req_count
    }
    
    return {
        "dest": dest,
        "finding": finding,
        "evidence": evidence_records,
        "tariff_details": tariff_details
    }


async def run_market_access(
    objective: str,
    inputs: Dict[str, Any],
    constraints: Dict[str, Any]
) -> SubagentFinding:
    """Research applied tariffs, preferential origin rules, and SPS/TBT requirements in parallel."""
    hs_code = inputs.get("hs_code", "090121")
    origin = inputs.get("origin", "IND")
    destinations = inputs.get("destinations", ["DEU"])
    
    # Execute across all destinations concurrently
    dest_tasks = [_evaluate_destination_market_access(dest, hs_code, origin) for dest in destinations]
    dest_results = await asyncio.gather(*dest_tasks)
    
    findings = []
    evidence_records: List[EvidenceRecord] = []
    calculations = {}
    
    for res in dest_results:
        dest = res["dest"]
        findings.append(res["finding"])
        evidence_records.extend(res["evidence"])
        calculations[f"{dest}_tariff_details"] = res["tariff_details"]
        
    return SubagentFinding(
        agent_name="MarketAccessAgent",
        objective=objective,
        findings=findings,
        evidence=evidence_records,
        calculations=calculations,
        limitations=[],
        follow_up_tasks=[]
    )
