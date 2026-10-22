"""Unit tests for deterministic arithmetic tools (CAGR, HHI, Multi-Criteria Scoring)."""

import pytest
from tradepilot.tools.analytics_tools import (
    calculate_demand_growth,
    calculate_supplier_concentration,
    score_export_markets
)


def test_calculate_demand_growth():
    """Verify CAGR calculation produces exact mathematical result."""
    # 2020: 1000, 2023: 1331 -> (1331/1000)^(1/3) - 1 = 1.10 - 1 = 10%
    obs = [
        {"year": 2020, "value": 1000.0},
        {"year": 2021, "value": 1100.0},
        {"year": 2022, "value": 1210.0},
        {"year": 2023, "value": 1331.0}
    ]
    res = calculate_demand_growth(obs)
    assert res["cagr_percent"] == 10.0
    assert res["absolute_growth"] == 331.0
    assert res["start_year"] == 2020
    assert res["end_year"] == 2023
    assert len(res["data_quality_flags"]) == 0


def test_calculate_demand_growth_insufficient_data():
    """Test handling of single observation."""
    obs = [{"year": 2023, "value": 500.0}]
    res = calculate_demand_growth(obs)
    assert res["cagr_percent"] == 0.0
    assert len(res["data_quality_flags"]) > 0


def test_calculate_supplier_concentration_hhi():
    """Verify HHI calculation and concentration classification."""
    # Shares: ITA 50% -> 2500, CHE 30% -> 900, POL 20% -> 400. Total HHI = 3800 (Highly Concentrated)
    partner_vals = {
        "ITA": 500.0,
        "CHE": 300.0,
        "POL": 200.0
    }
    res = calculate_supplier_concentration(partner_vals)
    assert res["hhi_score"] == 3800.0
    assert res["concentration_category"] == "Highly Concentrated"
    assert res["cr3_share_percent"] == 100.0
    assert len(res["top_suppliers"]) == 3


def test_score_export_markets_ranking():
    """Verify deterministic ranking of candidate destinations."""
    markets = [
        {
            "country": "DEU",
            "country_name": "Germany",
            "market_size_usd": 3000000000,
            "cagr_percent": 6.5,
            "applied_tariff_percent": 7.5,
            "hhi": 1400,
            "gdp_growth_percent": 1.0
        },
        {
            "country": "USA",
            "country_name": "United States",
            "market_size_usd": 2500000000,
            "cagr_percent": 8.0,
            "applied_tariff_percent": 0.0,
            "hhi": 1200,
            "gdp_growth_percent": 2.5
        }
    ]
    res = score_export_markets(markets)
    assert res["status"] == "success"
    rankings = res["rankings"]
    assert len(rankings) == 2
    # Verify rankings are sorted by suitability_score descending
    assert rankings[0]["suitability_score"] >= rankings[1]["suitability_score"]
    assert rankings[0]["rank"] == 1
    assert rankings[1]["rank"] == 2
