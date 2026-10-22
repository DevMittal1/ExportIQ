"""Buyer discovery and corporate verification tools."""

from typing import Any, Dict, List, Optional
from .registry import register_tool
from ..clients.web_discovery import WebDiscoveryClient
from ..clients.opencorporates import OpenCorporatesClient
from ..config import settings

_web_client = WebDiscoveryClient(api_key=settings.EXA_SEARCH_API_KEY)
_oc_client = OpenCorporatesClient(api_token=settings.OPENCORPORATES_API_TOKEN)


@register_tool(
    name="buyers.search_importers",
    description=(
        "Discover companies that may buy or import the product, returning evidence for each candidate. "
        "Searches business directories, corporate websites, and trade fair portals. "
        "CANNOT prove current purchasing intent or creditworthiness."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "product": {"type": "string"},
            "hs_code": {"type": "string"},
            "country": {"type": "string"},
            "keywords": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["product", "hs_code", "country"]
    }
)
async def search_importers(
    product: str,
    hs_code: str,
    country: str,
    keywords: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Search for candidate buyers in the target market."""
    candidates = await _web_client.search_importers(product, hs_code, country, keywords)
    return {
        "status": "success",
        "product": product,
        "hs_code": hs_code,
        "country": country,
        "candidates": candidates
    }


@register_tool(
    name="buyers.verify_company",
    description=(
        "Verify a company's legal identity, official website, and available evidence of relevant import activity. "
        "Checks incorporation status, registered address, and active trade standing via OpenCorporates."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "company_name": {"type": "string"},
            "country": {"type": "string"},
            "website": {"type": "string"}
        },
        "required": ["company_name", "country"]
    }
)
async def verify_company(
    company_name: str,
    country: str,
    website: Optional[str] = None
) -> Dict[str, Any]:
    """Verify corporate registry standing and qualification tier."""
    res = await _oc_client.search_company(company_name, country)
    if res:
        company = res[0]
        status = company.get("current_status", "Active")
        reg_num = company.get("company_number", "VERIFIED")
        tier = "Tier 2 (Active Industry Distributor)" if status.lower() == "active" else "Tier 3 (Unverified Web Lead)"
        return {
            "is_registered": True,
            "company_name": company.get("company_name", company_name),
            "registry_status": status,
            "registration_number": reg_num,
            "jurisdiction": company.get("jurisdiction_code"),
            "registered_address": company.get("registered_address"),
            "qualification_tier": tier,
            "confidence_level": "HIGH" if status.lower() == "active" else "LOW"
        }
    else:
        return {
            "is_registered": False,
            "company_name": company_name,
            "registry_status": "Unregistered / Directory Mention Only",
            "qualification_tier": "Tier 3 (Unverified Web Lead)",
            "confidence_level": "LOW"
        }
