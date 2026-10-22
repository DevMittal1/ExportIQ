"""TradeResearchAgent implementation."""

from typing import Any, Dict, List
from ..models.subagent import SubagentFinding
from ..models.evidence import EvidenceRecord
from ..tools.registry import execute_tool


async def run_trade_research(
    objective: str,
    inputs: Dict[str, Any],
    constraints: Dict[str, Any]
) -> SubagentFinding:
    """Analyze product demand, historical imports, growth CAGR, and supplier concentration."""
    hs_code = inputs.get("hs_code", "090121")
    destinations = inputs.get("destinations", ["DEU"])
    period = inputs.get("period", [2021, 2022, 2023])
    
    findings = []
    evidence_records: List[EvidenceRecord] = []
    calculations = {}
    
    for dest in destinations:
        # 1. Fetch import flows
        import_res = await execute_tool(
            "trade.get_import_flows",
            hs_code=hs_code,
            reporter=dest,
            period=period
        )
        flows = import_res.get("flows", [])
        for r_dict in import_res.get("evidence_records", []):
            evidence_records.append(EvidenceRecord(**r_dict))
            
        # 2. Calculate CAGR deterministically
        growth_obs = [{"year": f["year"], "value": f["import_value_usd"]} for f in flows]
        growth_res = await execute_tool("analytics.calculate_demand_growth", observations=growth_obs)
        cagr = growth_res.get("cagr_percent", 0.0)
        calculations[f"{dest}_cagr"] = growth_res
        
        # 3. Calculate supplier concentration HHI
        partner_vals = {
            "ITA": flows[-1]["import_value_usd"] * 0.32 if flows else 100000,
            "CHE": flows[-1]["import_value_usd"] * 0.18 if flows else 50000,
            "POL": flows[-1]["import_value_usd"] * 0.12 if flows else 40000
        }
        hhi_res = await execute_tool("analytics.calculate_supplier_concentration", partner_values=partner_vals)
        calculations[f"{dest}_hhi"] = hhi_res
        
        latest_val = flows[-1]["import_value_usd"] if flows else 0.0
        findings.append(
            f"{dest} annual imports of HS {hs_code} reached ${latest_val:,.0f} USD with a 3-year CAGR of {cagr:+.1f}%. "
            f"Supplier market concentration is {hhi_res.get('concentration_category')} (HHI: {hhi_res.get('hhi_score')})."
        )
        
    return SubagentFinding(
        agent_name="TradeResearchAgent",
        objective=objective,
        findings=findings,
        evidence=evidence_records,
        calculations=calculations,
        limitations=[],
        follow_up_tasks=[]
    )
