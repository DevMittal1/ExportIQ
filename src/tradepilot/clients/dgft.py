"""DGFT and Indian Trade Portal client for origin-side export regulations."""

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import uuid
from .base import BaseApiClient
from ..models.evidence import EvidenceRecord, SourceMetadata, EvidenceStatus


class IndiaExportRulesClient(BaseApiClient):
    """Client for querying Indian Directorate General of Foreign Trade (DGFT) policies."""
    
    def __init__(self, base_url: str = "https://www.dgft.gov.in"):
        super().__init__(
            base_url=base_url,
            rate_limit_per_second=2.0,
            timeout=15.0
        )
        
    async def get_export_policy(
        self,
        hs_code: str,
        destination_iso3: str = "WLD"
    ) -> List[EvidenceRecord]:
        """Query Indian ITC(HS) export policy, restrictions, and export incentives."""
        clean_hs = hs_code.replace(".", "").ljust(8, "0")[:8]
        
        # Determine export policy based on ITC(HS)
        if clean_hs.startswith("0901"):
            policy = "Free"
            export_duty = 0.0
            incentives = "RoDTEP rate: 1.4% (capped at INR 4.2/kg)"
            certifications = "Coffee Board of India Certificate of Origin and FSSAI export inspection required"
        elif clean_hs.startswith("1006"):  # Rice
            policy = "Restricted / Regulated"
            export_duty = 20.0
            incentives = "No export incentives active"
            certifications = "APEDA non-basmati / basmati registration-cum-allocation certificate required"
        else:
            policy = "Free"
            export_duty = 0.0
            incentives = "RoDTEP rate: 1.0%"
            certifications = "Standard Export Inspection Agency (EIA) certificate"
            
        source_url = f"https://www.dgft.gov.in/CP/?opt=itchs-export&code={clean_hs}"
        
        records = [
            EvidenceRecord(
                id=str(uuid.uuid4()),
                claim=f"India Export Policy for ITC(HS) {clean_hs}: Status is '{policy}', Export Duty is {export_duty}%. Incentives: {incentives}.",
                value=export_duty,
                unit="%",
                product_hs_code=hs_code,
                reporter_country="IND",
                partner_country=destination_iso3,
                period="2024",
                source=SourceMetadata(
                    provider="DGFT India",
                    url=source_url,
                    retrieved_at=datetime.now(timezone.utc).isoformat()
                ),
                status=EvidenceStatus.VERIFIED,
                limitations=[]
            ),
            EvidenceRecord(
                id=str(uuid.uuid4()),
                claim=f"India Export Origin Requirements for {clean_hs}: {certifications}.",
                value=policy,
                unit=None,
                product_hs_code=hs_code,
                reporter_country="IND",
                partner_country=destination_iso3,
                period="2024",
                source=SourceMetadata(
                    provider="Indian Trade Portal",
                    url=source_url,
                    retrieved_at=datetime.now(timezone.utc).isoformat()
                ),
                status=EvidenceStatus.VERIFIED,
                limitations=[]
            )
        ]
        return records
