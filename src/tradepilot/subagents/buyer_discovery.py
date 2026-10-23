"""BuyerDiscoveryAgent implementation with batch tool execution."""

import asyncio
from typing import Any, Dict, List
from ..models.subagent import SubagentFinding
from ..tools.registry import execute_tool


async def _discover_buyers_for_destination(
    dest: str,
    product: str,
    hs_code: str
) -> Dict[str, Any]:
    """Search and batch-verify commercial importers concurrently for a single destination."""
    search_res = await execute_tool(
        "buyers.search_importers",
        product=product,
        hs_code=hs_code,
        country=dest
    )
    candidates = search_res.get("candidates", [])
    
    # Execute batch verification in a single tool call
    company_batch = [
        {
            "company_name": cand.get("company_name", "Lead"),
            "country": dest,
            "website": cand.get("website_url")
        }
        for cand in candidates
    ]
    
    if company_batch:
        verify_res = await execute_tool("buyers.verify_company", companies=company_batch)
        verified_leads = verify_res.get("results", [])
        dest_verified = verify_res.get("verified_count", 0)
    else:
        verified_leads = []
        dest_verified = 0
        
    finding = (
        f"Buyer discovery in {dest}: Identified {len(candidates)} prospective importers, with {dest_verified} verified in national registries."
    )
    
    return {
        "dest": dest,
        "finding": finding,
        "leads": verified_leads
    }


async def run_buyer_discovery(
    objective: str,
    inputs: Dict[str, Any],
    constraints: Dict[str, Any]
) -> SubagentFinding:
    """Discover and batch-verify candidate commercial importers in parallel across destinations."""
    product = inputs.get("product", "Specialty Coffee")
    hs_code = inputs.get("hs_code", "090121")
    destinations = inputs.get("destinations", ["DEU"])
    
    # Run buyer discovery across all destinations concurrently
    dest_tasks = [_discover_buyers_for_destination(dest, product, hs_code) for dest in destinations]
    dest_results = await asyncio.gather(*dest_tasks)
    
    findings = []
    calculations = {}
    
    for res in dest_results:
        dest = res["dest"]
        findings.append(res["finding"])
        calculations[f"{dest}_leads"] = res["leads"]
        
    return SubagentFinding(
        agent_name="BuyerDiscoveryAgent",
        objective=objective,
        findings=findings,
        evidence=[],
        calculations=calculations,
        limitations=[],
        follow_up_tasks=[]
    )
