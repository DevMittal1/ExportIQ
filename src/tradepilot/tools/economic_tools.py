"""Macroeconomic indicator tools querying the World Bank Indicators API."""

from typing import Any, Dict, List
from .registry import register_tool
from ..clients.worldbank import WorldBankClient

_wb_client = WorldBankClient()


@register_tool(
    name="economics.get_country_indicators",
    description=(
        "Retrieve macroeconomic indicators for candidate markets from the World Bank. "
        "Returns GDP (current USD), GDP growth rate (annual %), total population, and inflation rate (CPI). "
        "Use as contextual economic indicators to gauge market stability and purchasing capacity. "
        "CANNOT be used as a substitute for product-specific trade demand."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "country_codes": {
                "type": "array",
                "items": {"type": "string", "pattern": "^[A-Z]{3}$"},
                "description": "List of ISO-3 country codes to evaluate"
            },
            "indicator_codes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "World Bank indicator codes (e.g. NY.GDP.MKTP.CD, NY.GDP.MKTP.KD.ZG)"
            },
            "period": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Years to query (e.g. [2021, 2022, 2023])"
            }
        },
        "required": ["country_codes", "indicator_codes", "period"]
    }
)
async def get_country_indicators(
    country_codes: List[str],
    indicator_codes: List[str],
    period: List[int]
) -> Dict[str, Any]:
    """Retrieve macroeconomic indicators across countries and years."""
    start_y = min(period)
    end_y = max(period)
    
    results: Dict[str, Dict[str, Any]] = {}
    evidence_records = []
    
    for country in country_codes:
        results[country] = {}
        for ind in indicator_codes:
            recs = await _wb_client.get_indicator(country, ind, start_y, end_y)
            results[country][ind] = [
                {"year": r.period, "value": r.value, "unit": r.unit} for r in recs
            ]
            evidence_records.extend([r.model_dump() for r in recs])
            
    return {
        "status": "success",
        "indicators": results,
        "evidence_records": evidence_records
    }
