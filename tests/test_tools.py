"""Unit tests for agent-facing business tools."""

import pytest
from tradepilot.tools.registry import execute_tool, TOOL_REGISTRY


@pytest.mark.asyncio
async def test_tool_registry_completeness():
    """Verify all 16 required tools are properly registered."""
    expected_tools = [
        "trade.get_import_flows",
        "trade.get_export_flows",
        "economics.get_country_indicators",
        "tariffs.get_applied_rate",
        "tariffs.check_preferential_rate",
        "tariffs.check_origin_rules",
        "compliance.search_product_requirements",
        "buyers.search_importers",
        "buyers.verify_company",
        "analytics.calculate_demand_growth",
        "analytics.calculate_supplier_concentration",
        "analytics.score_export_markets",
        "evidence.verify_claim",
        "evidence.find_conflicts",
        "skills.read_skill",
        "research.delegate"
    ]
    for tool_name in expected_tools:
        assert tool_name in TOOL_REGISTRY, f"Missing tool: {tool_name}"


@pytest.mark.asyncio
async def test_trade_get_import_flows():
    """Test trade.get_import_flows tool execution."""
    res = await execute_tool(
        "trade.get_import_flows",
        hs_code="090121",
        reporter="DEU",
        period=[2021, 2022, 2023]
    )
    assert res["status"] == "success"
    assert res["reporter"] == "DEU"
    assert len(res["flows"]) == 3
    assert len(res["evidence_records"]) == 3


@pytest.mark.asyncio
async def test_tariffs_get_applied_rate():
    """Test tariffs.get_applied_rate tool execution."""
    res = await execute_tool(
        "tariffs.get_applied_rate",
        hs_code="090121",
        origin="IND",
        destination="DEU"
    )
    assert res["status"] == "success"
    assert "applied_rate_percent" in res
    assert res["source_authority"] != ""


@pytest.mark.asyncio
async def test_skills_read_skill():
    """Test skills.read_skill tool execution."""
    res = await execute_tool("skills.read_skill", skill_name="hs-classification")
    assert res["status"] == "success"
    assert "Harmonized System" in res["instructions"]
