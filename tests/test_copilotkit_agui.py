"""Tests for CopilotKit & AG-UI protocol integration and remote endpoints."""

import pytest
from fastapi.testclient import TestClient
from tradepilot.api.main import app


def test_copilotkit_info_endpoint():
    """Verify /copilotkit/info returns AG-UI compliant agent registry and frontend actions."""
    client = TestClient(app)
    resp = client.post("/copilotkit/info", json={})
    assert resp.status_code == 200
    
    data = resp.json()
    assert "agents" in data
    assert any(a["name"] == "tradepilot_agent" for a in data["agents"])
    agent = next(a for a in data["agents"] if a["name"] == "tradepilot_agent")
    assert agent["type"] == "langgraph_agui"
    assert "TradePilot" in agent["description"]

    # Verify registered frontend actions
    assert "actions" in data
    action_names = [act["name"] for act in data["actions"]]
    expected_actions = [
        "render_market_chart",
        "open_dossier_tab",
        "filter_buyers_directory",
        "apply_scoring_preset",
        "export_dossier_file",
    ]
    for ea in expected_actions:
        assert ea in action_names, f"Action {ea} missing from CopilotKit remote endpoint"


def test_ag_ui_alias_endpoint():
    """Verify /ag-ui/info endpoint returns the same AG-UI protocol discovery metadata."""
    client = TestClient(app)
    resp = client.post("/ag-ui/info", json={})
    assert resp.status_code == 200
    
    data = resp.json()
    assert any(a["name"] == "tradepilot_agent" for a in data["agents"])
    assert "actions" in data
    assert any(act["name"] == "render_market_chart" for act in data["actions"])


def test_frontend_root_endpoint():
    """Verify / and /app serve the interactive TradePilot Copilot UI with frontend tools."""
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "TradePilot AI" in resp.text
    assert "TradePilot Copilot" in resp.text
    assert "LangGraph Copilot Active" in resp.text

    # Verify Chart.js and dossier frontend tool markup are included
    assert "chart.umd.min.js" in resp.text
    assert "marketChartCanvas" in resp.text
    assert "dossierToolTabs" in resp.text
    assert "copilotToastContainer" in resp.text
    assert "render_market_chart" in resp.text
    assert "filter_buyers_directory" in resp.text
    assert "apply_scoring_preset" in resp.text
    assert "export_dossier_file" in resp.text

    resp_app = client.get("/app")
    assert resp_app.status_code == 200
    assert "TradePilot AI" in resp_app.text
    assert "marketChartCanvas" in resp_app.text


