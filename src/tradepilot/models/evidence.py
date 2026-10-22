"""Standard Evidence Record specification and contracts."""

from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, Field
import uuid
from datetime import datetime, timezone


class EvidenceStatus(str, Enum):
    """Validation status of an evidence record."""
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    CONFLICTED = "conflicted"
    PROVISIONAL = "provisional"


class SourceMetadata(BaseModel):
    """Metadata detailing the official provenance of a finding."""
    provider: str = Field(description="Name of the official API or registry provider")
    url: str = Field(description="Direct URL or API query endpoint of the retrieved source")
    retrieved_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO-8601 timestamp of data retrieval"
    )


class EvidenceRecord(BaseModel):
    """Universal normalized observation object representing empirical trade evidence."""
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique deterministic hash or UUID of the observation"
    )
    claim: str = Field(description="Concise factual statement summarizing the empirical finding")
    value: Any = Field(description="Normalized scalar value of the finding (float, int, str, bool)")
    unit: Optional[str] = Field(default=None, description="Standardized unit of measurement (USD, kg, %)")
    product_hs_code: str = Field(description="Harmonized System classification code tied to the evidence")
    reporter_country: str = Field(description="ISO-3 code of reporting country (e.g. DEU, USA)")
    partner_country: str = Field(description="ISO-3 code of partner country ('WLD' for world)")
    period: str = Field(description="Reference calendar period (e.g. '2023', '2021-2023')")
    source: SourceMetadata = Field(description="Provenance details")
    status: EvidenceStatus = Field(default=EvidenceStatus.UNVERIFIED, description="Verification status")
    limitations: List[str] = Field(default_factory=list, description="Known reporting lags or caveats")
