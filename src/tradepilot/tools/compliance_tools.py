"""Regulatory compliance and import requirement tools supporting single and batch queries."""

import asyncio
from typing import Any, Dict, List, Optional
from .registry import register_tool
from ..clients.eu_taric import EUTaricClient
from ..clients.dgft import IndiaExportRulesClient

_taric = EUTaricClient()
_dgft = IndiaExportRulesClient()


async def _search_single_destination_requirements(
    hs_code: str,
    orig: str,
    dest: str,
    keywords: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Retrieve compliance measures for a single destination."""
    requirements = []
    
    # Destination side checks (e.g. EU)
    if dest in ["DEU", "FRA", "ITA", "NLD", "ESP"]:
        eu_recs = await _taric.get_eu_measures(hs_code, orig, dest)
        for r in eu_recs:
            if "Requirements" in r.claim:
                requirements.append({
                    "category": "SPS / Regulatory Checklist",
                    "authority": "European Commission / EFSA",
                    "description": r.claim,
                    "mandatory_documents": [
                        "Phytosanitary Certificate",
                        "Commercial Invoice",
                        "Packing List",
                        "Single Administrative Document (SAD)"
                    ]
                })
    elif dest == "USA":
        requirements.append({
            "category": "FDA / USDA Compliance",
            "authority": "US FDA & USDA APHIS",
            "description": "Prior Notice of Imported Food shipments, FDA Food Facility Registration, and APHIS agricultural entry inspection.",
            "mandatory_documents": ["FDA Prior Notice Confirmation", "Customs Entry Form 7501"]
        })
        
    # Origin side checks (e.g. India)
    if orig == "IND":
        in_recs = await _dgft.get_export_policy(hs_code, dest)
        for r in in_recs:
            if "Origin Requirements" in r.claim:
                requirements.append({
                    "category": "Origin Export Clearances",
                    "authority": "DGFT & Commodity Export Boards",
                    "description": r.claim,
                    "mandatory_documents": ["Export Inspection Certificate", "Certificate of Origin"]
                })
                
    return {
        "status": "success",
        "hs_code": hs_code,
        "origin": orig,
        "destination": dest,
        "requirements": requirements
    }


@register_tool(
    name="compliance.search_product_requirements",
    description=(
        "Find official import requirements, restrictions, certifications, and relevant regulatory notices. "
        "Returns mandatory product certifications, testing standards, labeling rules, packaging directives, and competent inspection agencies. "
        "Supports querying single or multiple destination markets concurrently."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "hs_code": {"type": "string"},
            "origin": {"type": "string"},
            "destination": {"type": "string", "description": "Single ISO-3 destination code"},
            "destinations": {"type": "array", "items": {"type": "string"}, "description": "Batch of ISO-3 destination codes"},
            "keywords": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["hs_code", "origin"]
    }
)
async def search_product_requirements(
    hs_code: str,
    origin: str,
    destination: Optional[str] = None,
    destinations: Optional[List[str]] = None,
    keywords: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Retrieve regulatory compliance measures for destination(s)."""
    orig = origin.upper()
    
    # Batch processing
    if destinations:
        tasks = [_search_single_destination_requirements(hs_code, orig, d.upper(), keywords) for d in destinations]
        results = await asyncio.gather(*tasks)
        
        reqs_by_dest = {r["destination"]: r["requirements"] for r in results}
        all_reqs = []
        for r in results:
            all_reqs.extend(r.get("requirements", []))
            
        return {
            "status": "success",
            "is_batch": True,
            "hs_code": hs_code,
            "origin": origin,
            "destinations": destinations,
            "requirements_by_destination": reqs_by_dest,
            "requirements": all_reqs,
            "results": results
        }
        
    if not destination:
        raise ValueError("Either 'destination' or 'destinations' batch list must be provided.")
        
    return await _search_single_destination_requirements(hs_code, orig, destination.upper(), keywords)
