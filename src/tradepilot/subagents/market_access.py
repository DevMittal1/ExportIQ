"""MarketAccessAgent implementation."""

from typing import Any, Dict, List
from ..models.subagent import SubagentFinding
from ..models.evidence import EvidenceRecord
from ..tools.registry import execute_tool


async def run_market_access(
    objective: str,
    inputs: Dict[str, Any],
    constraints: Dict[str, Any]
) -> SubagentFinding:
    """Research applied tariffs, preferential origin rules, and SPS/TBT requirements."""
    hs_code = inputs.get("hs_code", "090121")
    origin = inputs.get("origin", "IND")
    destinations = inputs.get("destinations", ["DEU"])
    
    findings = []
    evidence_records: List[EvidenceRecord] = []
    calculations = {}
    
    for dest in destinations:
        # 1. Get applied MFN rate
        tariff_res = await execute_tool(
            "tariffs.get_applied_rate",
            hs_code=hs_code,
            origin=origin,
            destination=dest
        )
        applied_rate = tariff_res.get("applied_rate_percent", 0.0)
        for r_dict in tariff_res.get("evidence_records", []):
            evidence_records.append(EvidenceRecord(**r_dict))
            
        # 2. Check preferential agreement
        pref_res = await execute_tool(
            "tariffs.check_preferential_rate",
            hs_code=hs_code,
            origin=origin,
            destination=dest
        )
        
        # 3. Check compliance requirements
        comp_res = await execute_tool(
            "compliance.search_product_requirements",
            hs_code=hs_code,
            origin=origin,
            destination=dest
        )
        reqs = comp_res.get("requirements", [])
        req_count = len(reqs)
        
        pref_text = (
            f"Preferential rate under {pref_res.get('agreement_name')} is {pref_res.get('preferential_rate')}"
            if pref_res.get("is_preferential_available")
            else "No preferential trade agreement active"
        )
        
        findings.append(
            f"Market access for {dest}: Standard MFN tariff is {applied_rate}%. {pref_text}. "
            f"Identified {req_count} key regulatory compliance measures."
        )
        
        calculations[f"{dest}_tariff_details"] = {
            "applied_mfn": applied_rate,
            "preferential_available": pref_res.get("is_preferential_available", False),
            "requirements_count": req_count
        }
        
    return SubagentFinding(
        agent_name="MarketAccessAgent",
        objective=objective,
        findings=findings,
        evidence=evidence_records,
        calculations=calculations,
        limitations=[],
        follow_up_tasks=[]
    )
