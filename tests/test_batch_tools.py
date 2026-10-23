"""Unit tests for batch tool capabilities."""

import pytest
from tradepilot.tools.registry import execute_tool


@pytest.mark.asyncio
async def test_batch_verify_companies():
    """Verify buyers.verify_company processes a batch of companies simultaneously."""
    companies = [
        {"company_name": "Tchibo GmbH", "country": "DEU"},
        {"company_name": "Dallmayr", "country": "DEU"},
        {"company_name": "Starbucks Coffee Trading", "country": "CHE"}
    ]
    res = await execute_tool("buyers.verify_company", companies=companies)
    assert res["status"] == "success"
    assert res["is_batch"] is True
    assert res["batch_size"] == 3
    assert len(res["results"]) == 3
    for entry in res["results"]:
        assert "company_name" in entry
        assert "is_registered" in entry


@pytest.mark.asyncio
async def test_batch_tariffs_get_applied_rate():
    """Verify tariffs.get_applied_rate queries multiple destinations in a single batch call."""
    res = await execute_tool(
        "tariffs.get_applied_rate",
        hs_code="090121",
        origin="IND",
        destinations=["DEU", "USA"]
    )
    assert res["status"] == "success"
    assert res["is_batch"] is True
    assert len(res["destinations"]) == 2
    assert "DEU" in res["rates_by_destination"]
    assert "USA" in res["rates_by_destination"]
    assert len(res["evidence_records"]) > 0


@pytest.mark.asyncio
async def test_batch_compliance_requirements():
    """Verify compliance.search_product_requirements queries multiple destinations in batch."""
    res = await execute_tool(
        "compliance.search_product_requirements",
        hs_code="090121",
        origin="IND",
        destinations=["DEU", "USA"]
    )
    assert res["status"] == "success"
    assert res["is_batch"] is True
    assert "DEU" in res["requirements_by_destination"]
    assert "USA" in res["requirements_by_destination"]
    assert len(res["requirements"]) > 0


@pytest.mark.asyncio
async def test_batch_trade_import_flows():
    """Verify trade.get_import_flows queries multiple reporter destinations in batch."""
    res = await execute_tool(
        "trade.get_import_flows",
        hs_code="090121",
        reporters=["DEU", "USA"],
        period=[2022, 2023]
    )
    assert res["status"] == "success"
    assert res["is_batch"] is True
    assert "DEU" in res["flows_by_reporter"]
    assert "USA" in res["flows_by_reporter"]
    assert len(res["evidence_records"]) > 0
