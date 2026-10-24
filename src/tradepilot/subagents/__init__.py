"""Subagents module for TradePilot AI."""

from .base import dispatch_subagent as base_dispatch_subagent
from .dispatch import dispatch_subagent
from .trade_research import run_trade_research
from .market_access import run_market_access
from .buyer_discovery import run_buyer_discovery
from .evidence_verification import run_evidence_verification
from .trade_advisory import run_trade_advisory
from .factory import build_subagent, SUBAGENTS
from .orchestrator import (
    TradePilotOrchestrator,
    supervisor,
    build_supervisor,
    build_research_request,
    extract_findings,
    merge_evidence
)

__all__ = [
    "dispatch_subagent",
    "base_dispatch_subagent",
    "run_trade_research",
    "run_market_access",
    "run_buyer_discovery",
    "run_evidence_verification",
    "run_trade_advisory",
    "build_subagent",
    "SUBAGENTS",
    "TradePilotOrchestrator",
    "supervisor",
    "build_supervisor",
    "build_research_request",
    "extract_findings",
    "merge_evidence"
]
