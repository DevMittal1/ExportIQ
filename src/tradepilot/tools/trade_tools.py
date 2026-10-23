"""Trade statistics tools for import and export bilateral flow analysis supporting single and batch queries."""

import asyncio
from typing import Any, Dict, List, Optional
from .registry import register_tool
from ..clients.comtrade import UNComtradeClient
from ..config import settings

_comtrade_client = UNComtradeClient(api_key=settings.COMTRADE_API_KEY)


async def _get_single_import_flow(
    hs_code: str,
    reporter: str,
    period: List[int],
    partner: str
) -> Dict[str, Any]:
    """Retrieve import flows for a single reporter."""
    records = await _comtrade_client.get_trade_flows(
        hs_code=hs_code,
        reporter_iso3=reporter,
        period_years=period,
        partner_iso3=partner,
        flow_code="M"
    )
    
    flows = []
    for rec in records:
        flows.append({
            "year": int(rec.period),
            "partner": rec.partner_country,
            "import_value_usd": float(rec.value),
            "claim": rec.claim
        })
        
    return {
        "status": "success",
        "reporter": reporter,
        "hs_code": hs_code,
        "flows": flows,
        "evidence_records": [rec.model_dump() for rec in records],
        "provenance": {
            "provider": "UN Comtrade",
            "url": f"https://comtradeapi.un.org/data/v1/get/C/A/HS?reporter={reporter}&cmdCode={hs_code}"
        },
        "limitations": records[0].limitations if records else []
    }


@register_tool(
    name="trade.get_import_flows",
    description=(
        "Retrieve annual or multi-year import trade flows for a specific product HS code and destination country. "
        "Returns total import value in USD, physical quantity, top supplying partner countries, and year-over-year trade movements. "
        "Supports querying a single reporter destination or a batch of reporters simultaneously."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "hs_code": {"type": "string", "pattern": "^[0-9]{2,6}$", "description": "2, 4, or 6 digit HS code"},
            "reporter": {"type": "string", "description": "Single ISO-3 code of importing destination"},
            "reporters": {"type": "array", "items": {"type": "string"}, "description": "Batch of destination ISO-3 codes"},
            "period": {"type": "array", "items": {"type": "integer"}, "description": "List of calendar years"},
            "partners": {"type": "array", "items": {"type": "string"}, "default": ["WLD"], "description": "Supplying partner ISO-3 codes"}
        },
        "required": ["hs_code", "period"]
    }
)
async def get_import_flows(
    hs_code: str,
    period: List[int],
    reporter: Optional[str] = None,
    reporters: Optional[List[str]] = None,
    partners: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Execute import flows query for single or batch destinations."""
    partner = partners[0] if partners else "WLD"
    
    # Batch processing
    if reporters:
        tasks = [_get_single_import_flow(hs_code, r, period, partner) for r in reporters]
        batch_results = await asyncio.gather(*tasks)
        
        flows_by_reporter = {res["reporter"]: res["flows"] for res in batch_results}
        all_evidence = []
        for res in batch_results:
            all_evidence.extend(res["evidence_records"])
            
        return {
            "status": "success",
            "is_batch": True,
            "hs_code": hs_code,
            "reporters": reporters,
            "flows_by_reporter": flows_by_reporter,
            "results": batch_results,
            "evidence_records": all_evidence
        }
        
    if not reporter:
        raise ValueError("Either 'reporter' or 'reporters' batch list must be provided.")
        
    return await _get_single_import_flow(hs_code, reporter, period, partner)


@register_tool(
    name="trade.get_export_flows",
    description=(
        "Retrieve export statistics for a supplying country to compare competitor market shares across destinations. "
        "Returns export volumes, destination distribution, and unit values. "
        "Use this to benchmark your origin country against competing global suppliers. "
        "CANNOT verify freight shipping routes or transit transshipment points."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "hs_code": {"type": "string", "pattern": "^[0-9]{2,6}$", "description": "HS code"},
            "reporter": {"type": "string", "pattern": "^[A-Z]{3}$", "description": "Origin supplying country ISO-3"},
            "partners": {"type": "array", "items": {"type": "string"}, "description": "Destination country ISO-3 codes"},
            "period": {"type": "array", "items": {"type": "integer"}, "description": "Calendar years to query"}
        },
        "required": ["hs_code", "reporter", "period"]
    }
)
async def get_export_flows(
    hs_code: str,
    reporter: str,
    period: List[int],
    partners: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Execute export flows query via UN Comtrade client."""
    partner = partners[0] if partners else "WLD"
    records = await _comtrade_client.get_trade_flows(
        hs_code=hs_code,
        reporter_iso3=reporter,
        period_years=period,
        partner_iso3=partner,
        flow_code="X"
    )
    
    flows = []
    for rec in records:
        flows.append({
            "year": int(rec.period),
            "destination": rec.partner_country,
            "export_value_usd": float(rec.value),
            "claim": rec.claim
        })
        
    return {
        "status": "success",
        "origin": reporter,
        "hs_code": hs_code,
        "flows": flows,
        "evidence_records": [rec.model_dump() for rec in records]
    }
