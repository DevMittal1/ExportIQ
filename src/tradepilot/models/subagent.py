"""Subagent task, finding, and registry contracts."""

from typing import Any, Dict, List
from pydantic import BaseModel, Field
from .evidence import EvidenceRecord


class SubagentTask(BaseModel):
    """Specification of a bounded task dispatched to a worker subagent."""
    agent_name: str = Field(description="Target subagent identifier")
    objective: str = Field(description="Concise operational goal for the subagent")
    inputs: Dict[str, Any] = Field(description="Task parameters (e.g. hs_code, countries, periods)")
    max_tool_calls: int = Field(default=10, description="Hard cap on tool executions")
    timeout_seconds: int = Field(default=60, description="Execution timeout in seconds")


class SubagentFinding(BaseModel):
    """Standardized output returned by a worker subagent to the Orchestrator."""
    agent_name: str = Field(description="Name of the producing subagent")
    objective: str = Field(description="Original assigned objective")
    findings: List[str] = Field(description="Concise factual narrative conclusions")
    evidence: List[EvidenceRecord] = Field(default_factory=list, description="Source-linked evidence records")
    calculations: Dict[str, Any] = Field(default_factory=dict, description="Deterministic formulas, inputs and results")
    limitations: List[str] = Field(default_factory=list, description="Known data gaps or caveats")
    follow_up_tasks: List[str] = Field(default_factory=list, description="Recommended additional investigations")


AGENT_REGISTRY: Dict[str, Dict[str, Any]] = {
    "trade_research": {
        "name": "TradeResearchAgent",
        "description": "Analyze product demand, import growth, supplier concentration, and market size.",
        "skills": ["trade-data-analysis", "hs-classification"],
        "tools": [
            "trade.get_import_flows",
            "trade.get_export_flows",
            "economics.get_country_indicators",
            "analytics.calculate_demand_growth",
            "analytics.calculate_supplier_concentration"
        ],
        "max_tool_calls": 10,
        "timeout_seconds": 45
    },
    "market_access": {
        "name": "MarketAccessAgent",
        "description": "Research tariffs, preferential rules of origin, SPS/TBT compliance, and import restrictions.",
        "skills": ["tariff-market-access"],
        "tools": [
            "tariffs.get_applied_rate",
            "tariffs.check_preferential_rate",
            "tariffs.check_origin_rules",
            "compliance.search_product_requirements"
        ],
        "max_tool_calls": 10,
        "timeout_seconds": 60
    },
    "buyer_discovery": {
        "name": "BuyerDiscoveryAgent",
        "description": "Discover and verify potential commercial importers, wholesale distributors, and buyers.",
        "skills": ["buyer-qualification"],
        "tools": [
            "buyers.search_importers",
            "buyers.verify_company"
        ],
        "max_tool_calls": 12,
        "timeout_seconds": 60
    },
    "evidence_verification": {
        "name": "EvidenceVerificationAgent",
        "description": "Audit claims, verify citations, cross-check statistics, and resolve contradictory source data.",
        "skills": ["trade-evidence-verification"],
        "tools": [
            "evidence.verify_claim",
            "evidence.find_conflicts"
        ],
        "max_tool_calls": 8,
        "timeout_seconds": 30
    }
}
