"""Comprehensive test suite for TradePilot LLM-driven ReAct Supervisor architecture."""

import pytest
from fastapi.testclient import TestClient

from tradepilot.models.subagent import SubagentTask, SubagentFinding, AGENT_REGISTRY
from tradepilot.models.evidence import EvidenceRecord
from tradepilot.subagents.factory import instrument_tool, build_subagent, SUBAGENTS
from tradepilot.subagents.dispatch import dispatch_subagent, invoke_bounded, normalize_finding
from tradepilot.subagents.orchestrator import (
    validate_trade_plan,
    calculate_demand_growth,
    calculate_supplier_concentration,
    build_research_request,
    extract_findings,
    merge_evidence,
    build_supervisor,
    TradePilotOrchestrator
)
from tradepilot.graph.workflow import create_react_supervisor_graph
from tradepilot.models.state import TradePilotState
from tradepilot.api.main import app, execute_react_supervisor_research, ResearchRequest


def test_subagent_task_and_finding_contracts():
    """Verify contracts include task_id, explicit budget semantics, and default factories."""
    # SubagentTask defaults
    task = SubagentTask(
        agent_name="trade_research",
        objective="Analyze import CAGR for DEU"
    )
    assert task.task_id != ""
    assert task.max_tool_calls == 10
    assert task.timeout_seconds == 60
    assert task.inputs == {}

    # SubagentFinding defaults
    finding = SubagentFinding(
        task_id=task.task_id,
        agent_name="TradeResearchAgent",
        objective=task.objective,
        findings=["Germany coffee imports grew by 5.8% CAGR."]
    )
    assert finding.task_id == task.task_id
    assert len(finding.findings) == 1
    assert finding.evidence == []
    assert finding.calculations == {}
    assert finding.limitations == []
    assert finding.follow_up_tasks == []


@pytest.mark.asyncio
async def test_instrument_tool_budget_enforcement():
    """Verify instrument_tool enforces dispatch-level budget cap."""
    budget = {"max_calls": 2, "current_calls": 0}
    wrapped_tool = instrument_tool("tariffs.get_applied_rate", agent_key="market_access", budget_tracker=budget)
    
    # 1st call: OK
    res1 = await wrapped_tool.ainvoke({"hs_code": "090121", "origin": "IND", "destination": "DEU"})
    assert res1["status"] == "success"
    assert budget["current_calls"] == 1
    
    # 2nd call: OK
    res2 = await wrapped_tool.ainvoke({"hs_code": "090121", "origin": "IND", "destination": "USA"})
    assert res2["status"] == "success"
    assert budget["current_calls"] == 2
    
    # 3rd call: Must fail due to dispatch budget exceeded
    with pytest.raises(RuntimeError) as exc_info:
        await wrapped_tool.ainvoke({"hs_code": "090121", "origin": "IND", "destination": "FRA"})
    assert "Dispatch tool budget exceeded" in str(exc_info.value)


@pytest.mark.asyncio
async def test_dispatch_subagent_tool_execution():
    """Verify dispatch_subagent successfully runs a registered specialist and returns normalized findings."""
    res = await dispatch_subagent.ainvoke({
        "agent_name": "market_access",
        "objective": "Check tariffs for coffee into Germany",
        "inputs": {"hs_code": "090121", "origin": "IND", "destinations": ["DEU"]},
        "task_id": "test_task_101"
    })
    
    assert res["task_id"] == "test_task_101"
    assert res["agent_name"] == "MarketAccessAgent"
    assert len(res["findings"]) > 0
    assert len(res["evidence"]) > 0
    assert "DEU_tariff_details" in res["calculations"]


@pytest.mark.asyncio
async def test_repeated_specialist_dispatches():
    """Verify supervisor can call the same specialist repeatedly with refined inputs."""
    # Dispatch 1: Initial broad analysis
    finding_1 = await dispatch_subagent.ainvoke({
        "agent_name": "trade_research",
        "objective": "Analyze import demand in Germany",
        "inputs": {"hs_code": "090121", "destinations": ["DEU"], "period": [2021, 2022, 2023]},
        "task_id": "dispatch_step_1"
    })
    assert finding_1["task_id"] == "dispatch_step_1"
    assert "DEU_cagr" in finding_1["calculations"]
    
    # Dispatch 2: Refined follow-up query to USA
    finding_2 = await dispatch_subagent.ainvoke({
        "agent_name": "trade_research",
        "objective": "Analyze import demand in USA for comparison",
        "inputs": {"hs_code": "090121", "destinations": ["USA"], "period": [2021, 2022, 2023]},
        "task_id": "dispatch_step_2"
    })
    assert finding_2["task_id"] == "dispatch_step_2"
    assert "USA_cagr" in finding_2["calculations"]
    
    # Merge findings and evidence
    combined_findings = [finding_1, finding_2]
    evidence_pool = merge_evidence(combined_findings)
    assert len(evidence_pool) >= 2


@pytest.mark.asyncio
async def test_supervisor_deterministic_tools():
    """Verify supervisor's deterministic calculation and validation tools."""
    # 1. validate_trade_plan
    plan_check_incomplete = await validate_trade_plan.ainvoke({
        "destinations": ["DEU"],
        "completed_agents": ["trade_research"]
    })
    assert plan_check_incomplete["valid"] is False
    assert "market_access" in plan_check_incomplete["missing_investigations"]
    assert "evidence_verification" in plan_check_incomplete["missing_investigations"]
    
    plan_check_complete = await validate_trade_plan.ainvoke({
        "destinations": ["DEU"],
        "completed_agents": ["trade_research", "market_access", "evidence_verification"]
    })
    assert plan_check_complete["valid"] is True
    assert plan_check_complete["status"] == "ready_for_scoring"

    # 2. calculate_demand_growth
    cagr_res = await calculate_demand_growth.ainvoke({
        "observations": [{"year": 2021, "value": 100}, {"year": 2023, "value": 121}]
    })
    assert cagr_res["cagr_percent"] == 10.0
    
    # 3. calculate_supplier_concentration
    hhi_res = await calculate_supplier_concentration.ainvoke({
        "partner_values": {"USA": 500, "DEU": 500}
    })
    assert hhi_res["hhi_score"] == 5000


@pytest.mark.asyncio
async def test_react_supervisor_graph_pipeline():
    """Verify create_react_supervisor_graph executes through ReAct supervisor to deterministic scoring."""
    graph = create_react_supervisor_graph()
    
    state: TradePilotState = {
        "product_query": "Specialty Coffee",
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
        "shortlisted_destinations": ["DEU", "USA"],
        "market_rankings": [],
        "final_report_markdown": None
    }
    
    config = {"configurable": {"thread_id": "test_supervisor_graph_01"}}
    final_state = await graph.ainvoke(state, config=config)
    
    assert final_state["current_stage"] == "completed"
    assert len(final_state["subagent_findings"]) > 0
    assert len(final_state["evidence_pool"]) > 0
    assert len(final_state["market_rankings"]) == 2
    assert final_state["final_report_markdown"] is not None


@pytest.mark.asyncio
async def test_react_supervisor_api_endpoint():
    """Verify /api/v1/research/react runs directly through ReAct supervisor and returns report."""
    client = TestClient(app)
    payload = {
        "product_query": "Roasted Coffee",
        "hs_code": "090121",
        "origin_country": "IND",
        "candidate_destinations": ["DEU", "USA"],
        "reference_years": [2021, 2022, 2023]
    }
    
    resp = client.post("/api/v1/research/react", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert len(data["rankings"]) == 2
    assert data["evidence_count"] > 0
    assert "Export Intelligence & Market Feasibility Report" in data["report_markdown"]
