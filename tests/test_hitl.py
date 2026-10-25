"""Unit tests for TradePilot 3-Stage Human-in-the-Loop (HITL) Architecture.

Stages:
1. Clarification & Parameter Resolution (Origin country)
2. Market Shortlist & Plan Approval
3. Dossier Review & Multi-Criteria Weight Tuning
"""

import pytest
from fastapi.testclient import TestClient
from tradepilot.api.main import app
from tradepilot.graph.workflow import create_react_supervisor_graph
from tradepilot.models.state import TradePilotState
from langgraph.types import Command


@pytest.mark.asyncio
async def test_hitl_3_stage_graph_pipeline():
    """Verify LangGraph pauses at all 3 checkpoints when enable_hitl is True and resumes sequentially."""
    graph = create_react_supervisor_graph()
    
    # Initial state with missing origin_country to trigger Stage 1 (Clarification)
    state: TradePilotState = {
        "query": "Export specialty roasted coffee",
        "product_query": "Roasted Coffee",
        "hs_code": "090121",
        "origin_country": None,  # Triggers Checkpoint 1
        "candidate_destinations": [],
        "reference_years": [2021, 2022, 2023],
        "active_skills": [],
        "execution_plan": [],
        "current_stage": "initialized",
        "follow_up_count": 0,
        "critical_gaps": [],
        "user_interrupt_needed": False,
        "user_interrupt_prompt": None,
        "enable_hitl": True,
        "scoring_weights": None,
        "human_clarification_completed": False,
        "human_plan_approved": False,
        "human_review_completed": False,
        "market_metrics_cache": [],
        "evidence_pool": [],
        "subagent_findings": [],
        "direct_answer": None,
        "shortlisted_destinations": [],
        "market_rankings": [],
        "final_report_markdown": None
    }
    
    config = {"configurable": {"thread_id": "test_hitl_3stages_thread"}}
    
    # --- Checkpoint 1: Clarification ---
    step1_state = await graph.ainvoke(state, config=config)
    assert "__interrupt__" in step1_state
    int1 = step1_state["__interrupt__"][0].value
    assert int1["checkpoint"] == "clarification"
    assert "origin_country" in int1["missing_fields"]
    
    # Human clarifies origin_country = "IND"
    step2_state = await graph.ainvoke(
        Command(resume={"action": "clarify", "origin_country": "IND"}),
        config=config
    )
    
    # --- Checkpoint 2: Plan Approval ---
    assert "__interrupt__" in step2_state
    int2 = step2_state["__interrupt__"][0].value
    assert int2["checkpoint"] == "plan_approval"
    assert len(int2["candidate_destinations"]) > 0
    
    # Human approves candidate destinations = ["DEU", "USA"]
    step3_state = await graph.ainvoke(
        Command(resume={"action": "approve_plan", "selected_destinations": ["DEU", "USA"]}),
        config=config
    )
    
    # --- Checkpoint 3: Dossier Review & Weight Tuning ---
    assert "__interrupt__" in step3_state
    int3 = step3_state["__interrupt__"][0].value
    assert int3["checkpoint"] == "dossier_review"
    assert len(int3["rankings"]) > 0
    assert "weights" in int3
    
    # Human customizes weights (50% tariff advantage)
    custom_weights = {
        "market_size": 0.10,
        "demand_growth": 0.10,
        "tariff_advantage": 0.50,
        "supplier_competition": 0.15,
        "macro_stability": 0.15
    }
    final_state = await graph.ainvoke(
        Command(resume={"action": "adjust_weights", "weights": custom_weights}),
        config=config
    )
    
    # Finalization
    assert final_state["current_stage"] == "completed"
    assert final_state["human_clarification_completed"] is True
    assert final_state["human_plan_approved"] is True
    assert final_state["human_review_completed"] is True
    assert final_state["final_report_markdown"] is not None
    assert final_state["scoring_weights"]["tariff_advantage"] == 0.50


def test_hitl_api_full_multi_turn_flow():
    """Verify end-to-end API progression across all 3 checkpoints."""
    client = TestClient(app)
    thread_id = "test_api_3stage_hitl_session"
    
    # Turn 1: Initial query missing origin
    resp1 = client.post("/api/v1/research", json={
        "thread_id": thread_id,
        "query": "Where should I export roasted coffee?",
        "product_query": "Roasted Coffee",
        "enable_hitl": True
    })
    assert resp1.status_code == 200
    d1 = resp1.json()
    assert d1["status"] == "awaiting_human_review"
    assert d1["checkpoint"] in ["clarification", "plan_approval"]
    
    if d1["checkpoint"] == "clarification":
        # Turn 2: Resume with clarified origin
        resp2 = client.post("/api/v1/research/resume", json={
            "thread_id": thread_id,
            "action": "clarify",
            "origin_country": "IND"
        })
        assert resp2.status_code == 200
        d2 = resp2.json()
        assert d2["status"] == "awaiting_human_review"
        assert d2["checkpoint"] == "plan_approval"
        
        # Turn 3: Resume with approved destinations
        resp3 = client.post("/api/v1/research/resume", json={
            "thread_id": thread_id,
            "action": "approve_plan",
            "selected_destinations": ["DEU", "USA"]
        })
        assert resp3.status_code == 200
        d3 = resp3.json()
        assert d3["status"] == "awaiting_human_review"
        assert d3["checkpoint"] == "dossier_review"
        assert len(d3["rankings"]) > 0
    else:
        # LLM bypassed clarification and went straight to plan approval
        resp2 = client.post("/api/v1/research/resume", json={
            "thread_id": thread_id,
            "action": "approve_plan",
            "selected_destinations": ["DEU", "USA"]
        })
        assert resp2.status_code == 200
        d2 = resp2.json()
        assert d2["status"] == "awaiting_human_review"
        assert d2["checkpoint"] == "dossier_review"
        assert len(d2["rankings"]) > 0
    
    # Turn 4: Resume with adjusted weights & finalize
    resp4 = client.post("/api/v1/research/resume", json={
        "thread_id": thread_id,
        "action": "adjust_weights",
        "weights": {
            "market_size": 0.20,
            "demand_growth": 0.20,
            "tariff_advantage": 0.30,
            "supplier_competition": 0.15,
            "macro_stability": 0.15
        }
    })
    assert resp4.status_code == 200
    d4 = resp4.json()
    assert d4["status"] == "completed"
    assert len(d4["rankings"]) > 0
    assert "Export Intelligence & Market Feasibility Report" in d4["report_markdown"]
