"""TradePilot Orchestrator coordination and dynamic planning logic."""

from typing import Any, Dict, List
from ..models.state import TradePilotState


class TradePilotOrchestrator:
    """Master planner and dynamic research coordinator."""
    
    @staticmethod
    def create_initial_plan(state: TradePilotState) -> List[Dict[str, Any]]:
        """Formulate multi-stage execution plan supporting parallel and sequential execution."""
        product = state.get("product_query") or (state.get("query") if state.get("query") else None)
        origin = state.get("origin_country") or "IND"
        destinations = state.get("candidate_destinations") or []
        hs_code = state.get("hs_code") or "090121"
        intent = state.get("query_intent")
        query_text = state.get("query") or ""
        
        # Semantic intent deduction based on presence of entities
        if not intent:
            if not state.get("product_query") and not destinations and query_text:
                intent = "trade_advisory"
            else:
                intent = "comprehensive_feasibility"
                
        plan: List[Dict[str, Any]] = []
        step_idx = 1
        
        # Branch 1: Trade Advisory (Incoterms, trade finance, export procedures, logistics)
        if intent in ["trade_advisory", "general_advisory"]:
            plan.append({
                "step": step_idx,
                "agent": "trade_advisory",
                "parallel_group": 1,
                "objective": "Provide authoritative trade advisory guidance on international commerce, regulations, and logistics.",
                "inputs": {"query": query_text or product or "General Trade Advisory"}
            })
            step_idx += 1
            plan.append({
                "step": step_idx,
                "agent": "evidence_verification",
                "parallel_group": 2,
                "objective": "Audit evidence records and resolve statistical conflicts.",
                "inputs": {}
            })
            return plan

        # Branch 2: Targeted Market Access / Compliance Only
        if intent == "market_access_only":
            active_destinations = destinations or ["USA", "DEU"]
            plan.append({
                "step": step_idx,
                "agent": "market_access",
                "parallel_group": 1,
                "objective": f"Evaluate MFN duties, preferential FTAs, and SPS/TBT import requirements for exports from {origin} to {active_destinations}.",
                "inputs": {
                    "hs_code": hs_code,
                    "origin": origin,
                    "destinations": active_destinations
                }
            })
            step_idx += 1
            plan.append({
                "step": step_idx,
                "agent": "evidence_verification",
                "parallel_group": 2,
                "objective": "Audit collected regulatory evidence.",
                "inputs": {}
            })
            return plan

        # Branch 3: Buyer Discovery Only
        if intent == "buyer_discovery_only":
            active_destinations = destinations or ["USA", "DEU"]
            plan.append({
                "step": step_idx,
                "agent": "buyer_discovery",
                "parallel_group": 1,
                "objective": f"Discover and verify active commercial importers and distributors for {product or 'Goods'} in {active_destinations}.",
                "inputs": {
                    "product": product or "General Merchandise",
                    "hs_code": hs_code,
                    "destinations": active_destinations
                }
            })
            step_idx += 1
            plan.append({
                "step": step_idx,
                "agent": "evidence_verification",
                "parallel_group": 2,
                "objective": "Audit verified company registry records.",
                "inputs": {}
            })
            return plan

        # Branch 4: Comprehensive Feasibility & Opportunity Discovery (Default)
        active_destinations = destinations or ["USA", "DEU"]
        effective_product = product or "General Merchandise"
        
        # Parallel Execution Tier (Phase 1: independent research subagents dispatched concurrently)
        plan.append({
            "step": 1,
            "agent": "trade_research",
            "parallel_group": 1,
            "objective": f"Analyze import demand, historical volume CAGR, and supplier competition for HS {hs_code} across {active_destinations}.",
            "inputs": {
                "hs_code": hs_code,
                "destinations": active_destinations,
                "period": state.get("reference_years", [2021, 2022, 2023])
            }
        })
        plan.append({
            "step": 2,
            "agent": "market_access",
            "parallel_group": 1,
            "objective": f"Evaluate MFN duties, preferential FTAs, and SPS/TBT import requirements for exports from {origin} to {active_destinations}.",
            "inputs": {
                "hs_code": hs_code,
                "origin": origin,
                "destinations": active_destinations
            }
        })
        plan.append({
            "step": 3,
            "agent": "buyer_discovery",
            "parallel_group": 1,
            "objective": f"Discover and verify active commercial importers and distributors for {effective_product} in shortlisted markets.",
            "inputs": {
                "product": effective_product,
                "hs_code": hs_code,
                "destinations": active_destinations
            }
        })
        
        # Sequential Execution Tier (Phase 2: audit and conflict verification)
        plan.append({
            "step": 4,
            "agent": "evidence_verification",
            "parallel_group": 2,
            "objective": "Audit all collected evidence for source validity, freshness, and cross-source variances.",
            "inputs": {}
        })
        
        return plan
