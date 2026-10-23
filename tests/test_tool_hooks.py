"""Unit tests for pre-tool and post-tool hook lifecycle and API usage tracking."""

import pytest
from tradepilot.tools.registry import execute_tool
from tradepilot.middleware.tool_hooks import (
    USAGE_TRACKER,
    ToolBudgetExceededError,
    ToolAuthorizationError
)


@pytest.fixture(autouse=True)
def clean_usage_tracker():
    """Reset the usage tracker metrics before each test."""
    USAGE_TRACKER.reset()
    yield
    USAGE_TRACKER.reset()


@pytest.mark.asyncio
async def test_tool_execution_hooks_tracking():
    """Verify pre_tool_hook and post_tool_hook record invocation, latency, and success metrics."""
    res = await execute_tool(
        "tariffs.get_applied_rate",
        hs_code="090121",
        origin="IND",
        destination="DEU"
    )
    assert res["status"] == "success"
    
    summary = USAGE_TRACKER.get_summary()
    assert summary["total_tool_invocations"] == 1
    assert summary["total_tool_errors"] == 0
    assert "tariffs.get_applied_rate" in summary["tools"]
    
    tool_stat = summary["tools"]["tariffs.get_applied_rate"]
    assert tool_stat["total_calls"] == 1
    assert tool_stat["successful_calls"] == 1
    assert tool_stat["failed_calls"] == 0
    assert tool_stat["avg_latency_ms"] >= 0.0


@pytest.mark.asyncio
async def test_tool_budget_enforcement():
    """Verify pre_tool_hook blocks execution and raises ToolBudgetExceededError when quota reached."""
    # Set limit to 2 calls
    USAGE_TRACKER.set_budget("tariffs.get_applied_rate", max_calls=2)
    
    # 1st call: OK
    await execute_tool("tariffs.get_applied_rate", hs_code="090121", origin="IND", destination="DEU")
    # 2nd call: OK
    await execute_tool("tariffs.get_applied_rate", hs_code="090121", origin="IND", destination="USA")
    
    # 3rd call: Must be blocked by pre_tool_hook
    with pytest.raises(ToolBudgetExceededError) as exc_info:
        await execute_tool("tariffs.get_applied_rate", hs_code="090121", origin="IND", destination="FRA")
        
    assert "exceeded execution budget limit of 2 calls" in str(exc_info.value)


@pytest.mark.asyncio
async def test_tool_authorization_enforcement():
    """Verify pre_tool_hook enforces agent permissions when agent_name is supplied."""
    # Trade research agent cannot call buyer discovery tool
    with pytest.raises(ToolAuthorizationError) as exc_info:
        await execute_tool(
            "buyers.search_importers",
            agent_name="trade_research",
            product="Coffee",
            hs_code="090121",
            country="DEU"
        )
    assert "not authorized to call tool" in str(exc_info.value)
    
    # But market access agent CAN call tariffs tool
    res = await execute_tool(
        "tariffs.get_applied_rate",
        agent_name="market_access",
        hs_code="090121",
        origin="IND",
        destination="DEU"
    )
    assert res["status"] == "success"


@pytest.mark.asyncio
async def test_persistent_db_and_api_endpoints():
    """Verify tool executions are stored in persistent SQLite and accessible via REST API and dashboard."""
    from fastapi.testclient import TestClient
    from tradepilot.api.main import app
    from tradepilot.db import USAGE_DB

    # Execute a tool call
    res = await execute_tool(
        "compliance.search_product_requirements",
        agent_name="market_access",
        hs_code="090121",
        origin="IND",
        destination="DEU"
    )
    assert res["status"] == "success"

    # Verify persistent DB has the log
    db_logs = USAGE_DB.get_logs(tool_name="compliance.search_product_requirements")
    assert len(db_logs) >= 1
    assert db_logs[0]["tool_name"] == "compliance.search_product_requirements"
    assert db_logs[0]["status"] == "success"
    assert db_logs[0]["duration_ms"] > 0

    client = TestClient(app)

    # 1. Test Dashboard UI endpoint
    dash_resp = client.get("/dashboard")
    assert dash_resp.status_code == 200
    assert "TradePilot AI" in dash_resp.text
    assert "TradePilot API Telemetry & Quota Plane" in dash_resp.text

    # 2. Test Metrics Summary API
    metrics_resp = client.get("/api/v1/metrics/api-usage")
    assert metrics_resp.status_code == 200
    m_data = metrics_resp.json()
    assert m_data["total_tool_invocations"] >= 1
    assert "compliance.search_product_requirements" in m_data["tools"]

    # 3. Test Logs API
    logs_resp = client.get("/api/v1/metrics/logs")
    assert logs_resp.status_code == 200
    l_data = logs_resp.json()
    assert l_data["count"] >= 1
    assert l_data["logs"][0]["tool_name"] == "compliance.search_product_requirements"

    # 4. Test Budget Control API
    budget_resp = client.post("/api/v1/metrics/budget", json={"tool_name": "tariffs.get_applied_rate", "max_calls": 5})
    assert budget_resp.status_code == 200
    assert budget_resp.json()["max_calls"] == 5

    # Verify budget reflected in persistent DB and summary
    assert USAGE_DB.get_budgets().get("tariffs.get_applied_rate") == 5

    # 5. Test Reset API
    reset_resp = client.post("/api/v1/metrics/reset")
    assert reset_resp.status_code == 200
    assert len(USAGE_DB.get_logs()) == 0
    assert len(USAGE_DB.get_budgets()) == 0

