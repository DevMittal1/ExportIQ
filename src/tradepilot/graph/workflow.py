"""StateGraph assembly and compilation for TradePilot AI with ReAct Supervisor topology."""

from typing import Any, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from ..models.state import TradePilotState
from .nodes import (
    validate_request_node,
    react_supervisor_node,
    deterministic_scoring_node,
    generate_report_node
)
from .edges import route_after_validation


def create_react_supervisor_graph(checkpointer: Optional[Any] = None) -> Any:
    """Build and compile the LLM-driven ReAct Supervisor topology with deterministic finalization.
    
    Topology:
      [validate_request] -> [react_supervisor] -> [deterministic_scoring] -> [generate_report] -> [END]
    """
    workflow = StateGraph(TradePilotState)
    
    workflow.add_node("validate_request", validate_request_node)
    workflow.add_node("react_supervisor", react_supervisor_node)
    workflow.add_node("deterministic_scoring", deterministic_scoring_node)
    workflow.add_node("generate_report", generate_report_node)
    
    workflow.add_edge(START, "validate_request")
    workflow.add_conditional_edges(
        "validate_request",
        route_after_validation,
        {
            "orchestrator_planning": "react_supervisor",
            "__end__": END
        }
    )
    workflow.add_edge("react_supervisor", "deterministic_scoring")
    workflow.add_edge("deterministic_scoring", "generate_report")
    workflow.add_edge("generate_report", END)
    
    cp = checkpointer or MemorySaver()
    return workflow.compile(checkpointer=cp)


def create_tradepilot_graph(checkpointer: Optional[Any] = None) -> Any:
    """Default workflow builder returning the ReAct supervisor graph topology."""
    return create_react_supervisor_graph(checkpointer=checkpointer)
