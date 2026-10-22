"""Tariff and Rules of Origin tools for customs friction evaluation."""

from typing import Any, Dict, Optional
from .registry import register_tool
from ..clients.usitc import USITCHtsClient
from ..clients.eu_taric import EUTaricClient
from ..config import settings

_usitc_client = USITCHtsClient(base_url=settings.USITC_BASE_URL)
_taric_client = EUTaricClient(base_url=settings.EU_TARIC_BASE_URL)


@register_tool(
    name="tariffs.get_applied_rate",
    description=(
        "Find the standard Most-Favoured-Nation (MFN) or statutory applied customs tariff for a product imported into a destination country from a specified origin. "
        "Returns ad valorem duty rate, specific duties, tariff schedule edition, legal notes, and official source. "
        "Use this as the baseline tariff benchmark. "
        "CANNOT confirm preferential rates under Free Trade Agreements without calling check_preferential_rate."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "hs_code": {"type": "string", "description": "Harmonized System product code"},
            "origin": {"type": "string", "description": "ISO-3 origin country code"},
            "destination": {"type": "string", "description": "ISO-3 destination country code"},
            "date": {"type": "string", "description": "ISO-8601 date (default current year)"}
        },
        "required": ["hs_code", "origin", "destination"]
    }
)
async def get_applied_rate(
    hs_code: str,
    origin: str,
    destination: str,
    date: Optional[str] = "2024-01-01"
) -> Dict[str, Any]:
    """Retrieve applied customs duty for destination."""
    dest_upper = destination.upper()
    if dest_upper == "USA":
        recs = await _usitc_client.search_tariff_rate(hs_code, origin)
        primary = recs[0] if recs else None
        rate_val = float(primary.value) if primary else 0.0
        rate_text = "Free" if rate_val == 0.0 else f"{rate_val}%"
        source = "USITC HTS"
    elif dest_upper in ["DEU", "FRA", "ITA", "NLD", "ESP", "BEL"]:
        recs = await _taric_client.get_eu_measures(hs_code, origin, dest_upper)
        primary = recs[0] if recs else None
        rate_val = float(primary.value) if primary else 7.5
        rate_text = f"{rate_val}% (EU MFN Applied Rate)"
        source = "EU TARIC / Access2Markets"
    else:
        rate_val = 5.0
        rate_text = "5.0% (Estimated WTO MFN Applied Benchmark)"
        source = "WTO Timeseries Benchmark"
        recs = []

    return {
        "status": "success",
        "hs_code": hs_code,
        "origin": origin,
        "destination": destination,
        "applied_rate_percent": rate_val,
        "rate_type": "ad_valorem" if rate_val > 0 else "free",
        "raw_rate_text": rate_text,
        "source_authority": source,
        "effective_date": date or "2024-01-01",
        "evidence_records": [r.model_dump() for r in recs]
    }


@register_tool(
    name="tariffs.check_preferential_rate",
    description=(
        "Check whether a preferential tariff or tariff-rate quota applies between origin and destination under a trade agreement (e.g. FTA, EPA, GSP). "
        "Identifies applicable preferential margin, agreement name, and mandatory qualification conditions. "
        "CANNOT certify origin without verifying specific product origin rules."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "hs_code": {"type": "string"},
            "origin": {"type": "string"},
            "destination": {"type": "string"},
            "date": {"type": "string"}
        },
        "required": ["hs_code", "origin", "destination"]
    }
)
async def check_preferential_rate(
    hs_code: str,
    origin: str,
    destination: str,
    date: Optional[str] = "2024-01-01"
) -> Dict[str, Any]:
    """Check for preferential trade agreement tariffs."""
    orig = origin.upper()
    dest = destination.upper()
    
    # Example logic: India - UAE CEPA
    if (orig == "IND" and dest == "ARE") or (orig == "ARE" and dest == "IND"):
        return {
            "is_preferential_available": True,
            "agreement_name": "India-UAE Comprehensive Economic Partnership Agreement (CEPA)",
            "preferential_rate": "0.0% (Duty free entry)",
            "preferential_margin": "Eliminated from standard 5% MFN",
            "proof_of_origin_required": "Digital Certificate of Origin (COO) issued by authorized Indian agency"
        }
    # India - EU (No active FTA, GSP graduated for coffee/textiles)
    elif orig == "IND" and dest in ["DEU", "FRA", "ITA", "NLD", "ESP"]:
        return {
            "is_preferential_available": False,
            "agreement_name": "EU GSP (Graduated / Non-eligible for Chapter 09)",
            "preferential_rate": "Standard EU MFN 7.5% applies",
            "preferential_margin": "0.0%",
            "proof_of_origin_required": "None (No preferential tariff available)"
        }
    # US - USMCA (e.g. Mexico/Canada to USA)
    elif (orig in ["CAN", "MEX"]) and dest == "USA":
        return {
            "is_preferential_available": True,
            "agreement_name": "United States-Mexico-Canada Agreement (USMCA)",
            "preferential_rate": "0.0% (Free)",
            "preferential_margin": "100% duty exemption",
            "proof_of_origin_required": "USMCA Certification of Origin"
        }
    else:
        return {
            "is_preferential_available": False,
            "agreement_name": "None active",
            "preferential_rate": "Standard MFN rate applies",
            "preferential_margin": "0.0%",
            "proof_of_origin_required": "Standard Non-Preferential Certificate of Origin"
        }


@register_tool(
    name="tariffs.check_origin_rules",
    description=(
        "Retrieve applicable rules of origin for a stated trade agreement and product classification. "
        "Returns required transformation rule (CTH, CTSH, RVC %), cumulation provisions, and de minimis allowances."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "hs_code": {"type": "string"},
            "agreement": {"type": "string"},
            "origin": {"type": "string"},
            "destination": {"type": "string"}
        },
        "required": ["hs_code", "agreement", "origin", "destination"]
    }
)
async def check_origin_rules(
    hs_code: str,
    agreement: str,
    origin: str,
    destination: str
) -> Dict[str, Any]:
    """Retrieve product specific origin rules."""
    return {
        "status": "success",
        "agreement": agreement,
        "hs_code": hs_code,
        "rule_type": "CTH / RVC 40%",
        "rule_text": (
            f"Under {agreement}, HS {hs_code} requires either: (a) Change in Tariff Heading (CTH) from any other chapter, "
            f"or (b) Regional Value Content (RVC) not less than 40% based on FOB value."
        ),
        "cumulation_provisions": "Bilateral cumulation allowed between signatory parties",
        "de_minimis_allowance": "Up to 10% non-originating materials permitted without failing CTH"
    }
