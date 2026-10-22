"""BuyerDiscoveryAgent implementation."""

from typing import Any, Dict, List
from ..models.subagent import SubagentFinding
from ..tools.registry import execute_tool


async def run_buyer_discovery(
    objective: str,
    inputs: Dict[str, Any],
    constraints: Dict[str, Any]
) -> SubagentFinding:
    """Discover and verify candidate commercial importers in shortlisted destination markets."""
    product = inputs.get("product", "Specialty Coffee")
    hs_code = inputs.get("hs_code", "090121")
    destinations = inputs.get("destinations", ["DEU"])
    
    findings = []
    calculations = {}
    verified_leads = []
    
    for dest in destinations:
        search_res = await execute_tool(
            "buyers.search_importers",
            product=product,
            hs_code=hs_code,
            country=dest
        )
        candidates = search_res.get("candidates", [])
        
        dest_verified = 0
        for cand in candidates:
            c_name = cand.get("company_name", "Lead")
            verify_res = await execute_tool(
                "buyers.verify_company",
                company_name=c_name,
                country=dest
            )
            is_reg = verify_res.get("is_registered", False)
            if is_reg:
                dest_verified += 1
                
            lead_entry = {
                "company_name": c_name,
                "country": dest,
                "website": cand.get("website_url"),
                "status": verify_res.get("registry_status"),
                "tier": verify_res.get("qualification_tier"),
                "relevance": cand.get("evidence_snippet")
            }
            verified_leads.append(lead_entry)
            
        findings.append(
            f"Buyer discovery in {dest}: Identified {len(candidates)} prospective importers, with {dest_verified} verified in national registries."
        )
        calculations[f"{dest}_leads"] = verified_leads
        
    return SubagentFinding(
        agent_name="BuyerDiscoveryAgent",
        objective=objective,
        findings=findings,
        evidence=[],
        calculations=calculations,
        limitations=[],
        follow_up_tasks=[]
    )
