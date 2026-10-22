"""StateGraph assembly and compilation for TradePilot AI."""

from typing import Any, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from ..models.state import TradePilotState
from .nodes import (
    validate_request_node,
    orchestrator_planning_node,
    trade_research_node,
    market_access_node,
    buyer_discovery_node,
    evidence_verification_node,
    deterministic_scoring_node,
    generate_report_node
)
from .edges import route_after_validation, route_after_verification


def create_tradepilot_graph(checkpointer: Optional[Any] = None) -> Any:
    """Build and compile the multi-agent LangGraph workflow."""
    workflow = StateGraph(TradePilotState)
    
    # 1. Register Graph Nodes
    workflow.add_node("validate_request", validate_request_node)
    workflow.add_node("orchestrator_planning", orchestrator_planning_node)
    workflow.add_node("trade_research", trade_research_node)
    workflow.add_node("market_access", market_access_node)
    workflow.add_node("buyer_discovery", buyer_discovery_node)
    workflow.add_node("evidence_verification", evidence_verification_node)
    workflow.add_node("deterministic_scoring", deterministic_scoring_node)
    workflow.add_node("generate_report", generate_report_node)
    
    # 2. Add Edges & Conditional Routing
    workflow.add_edge(START, "validate_request")
    
    workflow.add_conditional_edges(
        "validate_request",
        route_after_validation,
        {
            "orchestrator_planning": "orchestrator_planning",
            "__end__": END
        }
    )
    
    # Sequential subagent execution pipeline
    workflow.add_edge("orchestrator_planning", "trade_research")
    workflow.add_edge("trade_research", "market_access")
    workflow.add_edge("market_access", "buyer_discovery")
    workflow.add_edge("buyer_discovery", "evidence_verification")
    
    workflow.add_conditional_edges(
        "evidence_verification",
        route_after_verification,
        {
            "targeted_follow_up": "trade_research",
            "deterministic_scoring": "deterministic_scoring"
        }
    )
    
    workflow.add_edge("deterministic_scoring", "generate_report")
    workflow.add_edge("generate_report", END)
    
    # Compile graph with memory saver if not provided
    cp = checkpointer or MemorySaver()
    return workflow.compile(checkpointer=cp)
