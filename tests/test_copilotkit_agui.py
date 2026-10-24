"""Tests for CopilotKit & AG-UI protocol integration and remote endpoints."""

import pytest
from fastapi.testclient import TestClient
from tradepilot.api.main import app


def test_copilotkit_info_endpoint():
    """Verify /copilotkit/info returns AG-UI compliant agent registry."""
    client = TestClient(app)
    resp = client.post("/copilotkit/info", json={})
    assert resp.status_code == 200
    
    data = resp.json()
    assert "agents" in data
    assert any(a["name"] == "tradepilot_agent" for a in data["agents"])
    agent = next(a for a in data["agents"] if a["name"] == "tradepilot_agent")
    assert agent["type"] == "langgraph_agui"
    assert "TradePilot" in agent["description"]


def test_ag_ui_alias_endpoint():
    """Verify /ag-ui/info endpoint returns the same AG-UI protocol discovery metadata."""
    client = TestClient(app)
    resp = client.post("/ag-ui/info", json={})
    assert resp.status_code == 200
    
    data = resp.json()
    assert any(a["name"] == "tradepilot_agent" for a in data["agents"])


def test_frontend_root_endpoint():
    """Verify / and /app serve the interactive TradePilot Copilot UI."""
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "TradePilot AI" in resp.text
    assert "TradePilot Copilot" in resp.text
    assert "LangGraph Copilot Active" in resp.text

    resp_app = client.get("/app")
    assert resp_app.status_code == 200
    assert "TradePilot AI" in resp_app.text

