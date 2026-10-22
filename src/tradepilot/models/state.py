"""State schema for LangGraph execution graph."""

from typing import Annotated, Any, Dict, List, Optional
import operator
from typing_extensions import TypedDict
from .evidence import EvidenceRecord
from .subagent import SubagentFinding


class TradePilotState(TypedDict):
    """Complete execution state of the TradePilot LangGraph workflow."""
    
    # User Inputs & Query Definitions
    product_query: str
    hs_code: Optional[str]
    origin_country: str
    candidate_destinations: List[str]
    reference_years: List[int]
    
    # Workflow Execution State
    active_skills: List[str]
    execution_plan: List[Dict[str, Any]]
    current_stage: str
    follow_up_count: int
    critical_gaps: List[str]
    user_interrupt_needed: bool
    user_interrupt_prompt: Optional[str]
    
    # Aggregated Structured Findings (Appended across graph steps via operator.add)
    evidence_pool: Annotated[List[Dict[str, Any]], operator.add]
    subagent_findings: Annotated[List[Dict[str, Any]], operator.add]
    
    # Analytical Outcomes
    shortlisted_destinations: List[str]
    market_rankings: List[Dict[str, Any]]
    final_report_markdown: Optional[str]
