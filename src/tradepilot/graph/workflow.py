"""StateGraph assembly and compilation for TradePilot AI with ReAct Supervisor topology."""

from typing import Any, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from ..models.state import TradePilotState
from .nodes import (
    validate_request_node,
    human_clarification_node,
    react_supervisor_node,
    human_plan_approval_node,
    deterministic_scoring_node,
    human_dossier_review_node,
    generate_report_node
)
from .edges import route_after_validation


def create_react_supervisor_graph(checkpointer: Optional[Any] = None) -> Any:
    """Build and compile the LLM-driven ReAct Supervisor topology with 3-stage HITL oversight.
    
    Topology:
      [validate_request] -> [human_clarification] -> [react_supervisor] -> [human_plan_approval] -> [deterministic_scoring] -> [human_dossier_review] -> [generate_report] -> [END]
    """
    workflow = StateGraph(TradePilotState)
    
    workflow.add_node("validate_request", validate_request_node)
    workflow.add_node("human_clarification", human_clarification_node)
    workflow.add_node("react_supervisor", react_supervisor_node)
    workflow.add_node("human_plan_approval", human_plan_approval_node)
    workflow.add_node("deterministic_scoring", deterministic_scoring_node)
    workflow.add_node("human_dossier_review", human_dossier_review_node)
    workflow.add_node("generate_report", generate_report_node)
    
    workflow.add_edge(START, "validate_request")
    workflow.add_conditional_edges(
        "validate_request",
        route_after_validation,
        {
            "human_clarification": "human_clarification",
            "__end__": END
        }
    )
    workflow.add_edge("human_clarification", "react_supervisor")
    workflow.add_edge("react_supervisor", "human_plan_approval")
    workflow.add_edge("human_plan_approval", "deterministic_scoring")
    workflow.add_edge("deterministic_scoring", "human_dossier_review")
    workflow.add_edge("human_dossier_review", "generate_report")
    workflow.add_edge("generate_report", END)
    
    if checkpointer is not None:
        cp = checkpointer
    else:
        try:
            from ..db.postgres import get_postgres_checkpointer
            cp = get_postgres_checkpointer() or MemorySaver()
        except Exception:
            cp = MemorySaver()
            
    return workflow.compile(checkpointer=cp)


def create_tradepilot_graph(checkpointer: Optional[Any] = None) -> Any:
    """Default workflow builder returning the ReAct supervisor graph topology."""
    return create_react_supervisor_graph(checkpointer=checkpointer)
