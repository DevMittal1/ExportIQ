"""TradePilot Orchestrator coordination logic."""

from typing import Any, Dict, List
from ..models.subagent import SubagentFinding
from ..models.state import TradePilotState
from ..tools.registry import execute_tool


class TradePilotOrchestrator:
    """Master planner and research coordinator."""
    
    @staticmethod
    def create_initial_plan(state: TradePilotState) -> List[Dict[str, Any]]:
        """Formulate multi-stage execution plan."""
        product = state["product_query"]
        origin = state["origin_country"]
        destinations = state["candidate_destinations"]
        hs_code = state.get("hs_code", "090121")
        
        plan = [
            {
                "step": 1,
                "agent": "trade_research",
                "objective": f"Analyze import demand, historical volume CAGR, and supplier competition for HS {hs_code} across {destinations}.",
                "inputs": {
                    "hs_code": hs_code,
                    "destinations": destinations,
                    "period": state.get("reference_years", [2021, 2022, 2023])
                }
            },
            {
                "step": 2,
                "agent": "market_access",
                "objective": f"Evaluate MFN duties, preferential FTAs, and SPS/TBT import requirements for exports from {origin} to {destinations}.",
                "inputs": {
                    "hs_code": hs_code,
                    "origin": origin,
                    "destinations": destinations
                }
            },
            {
                "step": 3,
                "agent": "buyer_discovery",
                "objective": f"Discover and verify active commercial importers and distributors for {product} in shortlisted markets.",
                "inputs": {
                    "product": product,
                    "hs_code": hs_code,
                    "destinations": destinations
                }
            },
            {
                "step": 4,
                "agent": "evidence_verification",
                "objective": "Audit all collected evidence for source validity, freshness, and cross-source variances.",
                "inputs": {}
            }
        ]
        return plan
