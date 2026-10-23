"""Integration tests for flexible queries, dynamic planning, and parallel execution."""

import pytest
from tradepilot.graph.workflow import create_tradepilot_graph
from tradepilot.models.state import TradePilotState
from tradepilot.subagents.orchestrator import TradePilotOrchestrator


def test_dynamic_orchestrator_parallel_grouping():
    """Verify Orchestrator groups independent research subagents into parallel_group 1."""
    state: TradePilotState = {
        "product_query": "Roasted Coffee",
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
    plan = TradePilotOrchestrator.create_initial_plan(state)
    
    # Assert parallel group 1 contains trade_research, market_access, buyer_discovery
    group_1_agents = [p["agent"] for p in plan if p.get("parallel_group") == 1]
    assert "trade_research" in group_1_agents
    assert "market_access" in group_1_agents
    assert "buyer_discovery" in group_1_agents
    
    # Verification is in sequential group 2
    group_2_agents = [p["agent"] for p in plan if p.get("parallel_group") == 2]
    assert "evidence_verification" in group_2_agents


@pytest.mark.asyncio
async def test_pure_trade_advisory_query_without_product_or_destinations():
    """Verify system handles general trade advisory without requiring product/destinations."""
    graph = create_tradepilot_graph()
    
    initial_state: TradePilotState = {
        "query": "What is the difference between FOB and CIF Incoterms and how do letters of credit work?",
        "product_query": None,
        "hs_code": None,
        "origin_country": None,
        "candidate_destinations": [],
        "reference_years": [2021, 2022, 2023],
        "query_intent": None,
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
    
    config = {"configurable": {"thread_id": "test_advisory_run_01"}}
    final_state = await graph.ainvoke(initial_state, config=config)
    
    assert final_state["current_stage"] == "completed"
    assert final_state["user_interrupt_needed"] is False
    
    # Assert TradeAdvisoryAgent produced findings
    findings = final_state["subagent_findings"]
    agent_names = [f["agent_name"] for f in findings]
    assert "TradeAdvisoryAgent" in agent_names
    
    # Check advisory report markdown
    report = final_state["final_report_markdown"]
    assert report is not None
    assert "Trade Intelligence Advisory" in report
    assert "Incoterms" in report or "FOB" in report


@pytest.mark.asyncio
async def test_natural_language_market_discovery_query():
    """Verify query with product and origin but NO destinations automatically discovers candidates."""
    graph = create_tradepilot_graph()
    
    initial_state: TradePilotState = {
        "query": "I want to export specialty coffee from India. What are the best markets?",
        "product_query": "Specialty Coffee",
        "hs_code": "090121",
        "origin_country": "IND",
        "candidate_destinations": [],
        "reference_years": [2021, 2022, 2023],
        "query_intent": None,
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
    
    config = {"configurable": {"thread_id": "test_discovery_run_01"}}
    final_state = await graph.ainvoke(initial_state, config=config)
    
    assert final_state["current_stage"] == "completed"
    assert final_state["user_interrupt_needed"] is False
    
    # Market rankings generated
    assert len(final_state["market_rankings"]) > 0
    assert final_state["final_report_markdown"] is not None


@pytest.mark.asyncio
async def test_targeted_market_access_query():
    """Verify targeted regulatory / tariff query runs only relevant subagents."""
    graph = create_tradepilot_graph()
    
    initial_state: TradePilotState = {
        "query": "What are the import duties and compliance certifications for roasted coffee in Germany?",
        "product_query": "Roasted Coffee",
        "hs_code": "090121",
        "origin_country": "IND",
        "candidate_destinations": ["DEU"],
        "reference_years": [2021, 2022, 2023],
        "query_intent": "market_access_only",
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
    
    config = {"configurable": {"thread_id": "test_target_access_01"}}
    final_state = await graph.ainvoke(initial_state, config=config)
    
    assert final_state["current_stage"] == "completed"
    findings = final_state["subagent_findings"]
    agent_names = [f["agent_name"] for f in findings]
    assert "MarketAccessAgent" in agent_names
