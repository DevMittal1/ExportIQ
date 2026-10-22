"""Conditional routing logic and edge definitions."""

from typing import Literal
from ..models.state import TradePilotState


def route_after_validation(state: TradePilotState) -> Literal["orchestrator_planning", "__end__"]:
    """Route after input validation."""
    if state.get("user_interrupt_needed") or state.get("current_stage") == "input_error":
        return "__end__"
    return "orchestrator_planning"


def route_after_verification(state: TradePilotState) -> Literal["targeted_follow_up", "deterministic_scoring"]:
    """Decide whether to execute targeted follow-up or proceed to scoring."""
    critical_gaps = state.get("critical_gaps", [])
    follow_up_count = state.get("follow_up_count", 0)
    
    # Bounded retry: maximum 2 follow-ups
    if critical_gaps and follow_up_count < 2:
        return "targeted_follow_up"
    return "deterministic_scoring"
