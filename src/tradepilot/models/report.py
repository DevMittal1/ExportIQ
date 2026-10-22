"""Final synthesized report data structures."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DestinationRanking(BaseModel):
    """Ranked export destination with comparative metrics."""
    rank: int = Field(description="Suitability rank (1 is highest)")
    country_iso3: str = Field(description="ISO-3 destination country code")
    country_name: str = Field(description="Common destination country name")
    suitability_score: float = Field(description="Calculated composite suitability score (0-100)")
    market_size_usd: float = Field(description="Annual product import demand in USD")
    cagr_3yr_percent: float = Field(description="3-year compound annual growth rate %")
    applied_tariff: str = Field(description="Applicable customs tariff rate explanation")
    market_access_friction: str = Field(description="Friction level (LOW, MODERATE, HIGH, RESTRICTIVE)")
    top_competitors: List[str] = Field(description="Primary competing origins with market shares")
    qualified_buyer_leads: int = Field(default=0, description="Count of vetted commercial importer leads")


class MarketAccessDetail(BaseModel):
    """Specific regulatory and duty breakdown for a destination country."""
    mfn_tariff: str
    preferential_tariff: Optional[str] = None
    origin_rules_summary: Optional[str] = None
    sps_requirements: List[str] = Field(default_factory=list)
    mandatory_certifications: List[str] = Field(default_factory=list)


class BuyerLead(BaseModel):
    """Qualified commercial buyer entity in a destination market."""
    country: str
    company_name: str
    registration_status: str
    website: Optional[str] = None
    qualification_tier: str = Field(description="Tier 1 (Verified Importer), Tier 2 (Distributor), Tier 3 (Web Lead)")
    relevance_evidence: str


class ExportIntelligenceReport(BaseModel):
    """Complete synthesized cross-border export feasibility dossier."""
    executive_summary: str
    product_profile: Dict[str, Any]
    ranked_destinations: List[DestinationRanking]
    market_access_matrix: Dict[str, MarketAccessDetail]
    buyer_directory: List[BuyerLead]
    audit_trail: Dict[str, Any]
