"""Buyer discovery and corporate verification tools supporting single and batch queries."""

import asyncio
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
        "Supports single or multiple country searches in batch. "
        "CANNOT prove current purchasing intent or creditworthiness."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "product": {"type": "string"},
            "hs_code": {"type": "string"},
            "country": {"type": "string", "description": "Single ISO-3 country code"},
            "countries": {"type": "array", "items": {"type": "string"}, "description": "Batch of ISO-3 country codes"},
            "keywords": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["product", "hs_code"]
    }
)
async def search_importers(
    product: str,
    hs_code: str,
    country: Optional[str] = None,
    countries: Optional[List[str]] = None,
    keywords: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Search for candidate buyers in one or multiple target markets concurrently."""
    target_countries = countries or ([country] if country else ["DEU"])
    
    if len(target_countries) == 1:
        c_code = target_countries[0]
        candidates = await _web_client.search_importers(product, hs_code, c_code, keywords)
        return {
            "status": "success",
            "product": product,
            "hs_code": hs_code,
            "country": c_code,
            "candidates": candidates
        }
        
    # Batch multi-country search
    tasks = [_web_client.search_importers(product, hs_code, c, keywords) for c in target_countries]
    batch_results = await asyncio.gather(*tasks)
    
    grouped_candidates = {}
    all_candidates = []
    for c_code, c_list in zip(target_countries, batch_results):
        grouped_candidates[c_code] = c_list
        all_candidates.extend(c_list)
        
    return {
        "status": "success",
        "is_batch": True,
        "product": product,
        "hs_code": hs_code,
        "countries": target_countries,
        "candidates_by_country": grouped_candidates,
        "candidates": all_candidates
    }


async def _verify_single(
    company_name: str,
    country: str,
    website: Optional[str] = None
) -> Dict[str, Any]:
    """Verify single company against corporate registry."""
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
            "confidence_level": "HIGH" if status.lower() == "active" else "LOW",
            "country": country,
            "website": website
        }
    else:
        return {
            "is_registered": False,
            "company_name": company_name,
            "registry_status": "Unregistered / Directory Mention Only",
            "qualification_tier": "Tier 3 (Unverified Web Lead)",
            "confidence_level": "LOW",
            "country": country,
            "website": website
        }


@register_tool(
    name="buyers.verify_company",
    description=(
        "Verify a company's legal identity, official website, and active standing via OpenCorporates. "
        "Supports verifying a single company or a batch of companies simultaneously."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "company_name": {"type": "string", "description": "Single company name to verify"},
            "country": {"type": "string", "description": "Country ISO-3 code for single verification"},
            "website": {"type": "string", "description": "Optional website URL"},
            "companies": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "company_name": {"type": "string"},
                        "country": {"type": "string"},
                        "website": {"type": "string"}
                    },
                    "required": ["company_name", "country"]
                },
                "description": "Batch of companies to verify simultaneously"
            }
        }
    }
)
async def verify_company(
    company_name: Optional[str] = None,
    country: Optional[str] = None,
    website: Optional[str] = None,
    companies: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """Verify corporate registry standing for a single company or batch of companies."""
    # Batch processing
    if companies:
        tasks = [_verify_single(c["company_name"], c["country"], c.get("website")) for c in companies]
        batch_results = await asyncio.gather(*tasks)
        verified_count = sum(1 for r in batch_results if r["is_registered"])
        return {
            "status": "success",
            "is_batch": True,
            "batch_size": len(companies),
            "verified_count": verified_count,
            "results": batch_results
        }
        
    # Single company processing
    if not company_name or not country:
        raise ValueError("Either 'companies' batch list or both 'company_name' and 'country' must be provided.")
        
    return await _verify_single(company_name, country, website)
