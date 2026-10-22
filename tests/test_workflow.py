"""End-to-end integration test for the compiled LangGraph workflow."""

import pytest
from tradepilot.graph.workflow import create_tradepilot_graph
from tradepilot.models.state import TradePilotState


@pytest.mark.asyncio
async def test_full_workflow_execution():
    """Verify end-to-end execution of TradePilot LangGraph pipeline."""
    graph = create_tradepilot_graph()
    
    initial_state: TradePilotState = {
        "product_query": "Roasted Coffee Beans",
        "hs_code": "090121",
        "origin_country": "IND",
        "candidate_destinations": ["DEU", "USA"],
        "reference_years": [2021, 2022, 2023],
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
    
    config = {"configurable": {"thread_id": "test_e2e_run_01"}}
    final_state = await graph.ainvoke(initial_state, config=config)
    
    # Assert successful completion
    assert final_state["current_stage"] == "completed"
    assert final_state["user_interrupt_needed"] is False
    
    # Verify subagents contributed findings
    findings = final_state["subagent_findings"]
    agent_names = [f["agent_name"] for f in findings]
    assert "TradeResearchAgent" in agent_names
    assert "MarketAccessAgent" in agent_names
    assert "BuyerDiscoveryAgent" in agent_names
    assert "EvidenceVerificationAgent" in agent_names
    
    # Verify evidence pool accumulated records
    assert len(final_state["evidence_pool"]) > 0
    
    # Verify market rankings generated
    assert len(final_state["market_rankings"]) == 2
    assert final_state["market_rankings"][0]["rank"] == 1
    
    # Verify synthesized report markdown
    report = final_state["final_report_markdown"]
    assert report is not None
    assert "Export Intelligence & Market Feasibility Report" in report
    assert "Destination Suitability Rankings" in report
