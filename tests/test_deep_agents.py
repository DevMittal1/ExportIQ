"""Tests for Deep Agents supervisor harness in TradePilot."""

import pytest
from tradepilot.subagents.deep_supervisor import (
    build_deep_supervisor,
    get_deep_subagents,
    TradePilotDeepOrchestrator
)
from tradepilot.models.state import TradePilotState


def test_deep_subagents_configuration():
    """Verify all 5 registered specialists are configured as isolated subagents."""
    subagents = get_deep_subagents()
    names = [s["name"] for s in subagents]
    
    assert "trade_research" in names
    assert "market_access" in names
    assert "buyer_discovery" in names
    assert "evidence_verification" in names
    assert "trade_advisory" in names
    
    for s in subagents:
        assert s["mode"] == "isolated"
        assert len(s["description"]) > 0


def test_deep_supervisor_graph_compilation():
    """Verify create_deep_agent compiles with harness tools and deterministic calculation tools."""
    supervisor = build_deep_supervisor()
    
    assert "tools" in supervisor.nodes
    tool_node = supervisor.nodes["tools"].bound
    
    registered_tools = list(tool_node.tools_by_name.keys())
    
    # Deep Agents harness built-in tools
    assert "task" in registered_tools
    assert "read_file" in registered_tools
    assert "write_file" in registered_tools
    
    # TradePilot deterministic tools
    assert "validate_trade_plan" in registered_tools
    assert "calculate_demand_growth" in registered_tools
    assert "calculate_supplier_concentration" in registered_tools


@pytest.mark.asyncio
async def test_deep_supervisor_execution_lifecycle():
    """Verify execution of Deep Supervisor on an export research task."""
    state: TradePilotState = {
        "query": "Evaluate export viability and tariffs for coffee in Germany",
        "product_query": "Roasted Coffee",
        "hs_code": "090121",
        "origin_country": "IND",
        "candidate_destinations": ["DEU"],
        "reference_years": [2021, 2022, 2023],
        "query_intent": "comprehensive_feasibility",
        "active_skills": [],
        "execution_plan": [],
        "current_stage": "initialized",
        "follow_up_count": 0,
        "critical_gaps": [],
        "user_interrupt_needed": False,
        "user_interrupt_prompt": None,
        "evidence_pool": [],
        "subagent_findings": [],
        "shortlisted_destinations": [],
        "market_rankings": [],
        "final_report_markdown": None
    }
    
    result = await TradePilotDeepOrchestrator.run_deep_supervisor(state, max_iterations=25)
    
    assert result["current_stage"] == "deep_supervisor_completed"
    assert "subagent_findings" in result
    assert "evidence_pool" in result
