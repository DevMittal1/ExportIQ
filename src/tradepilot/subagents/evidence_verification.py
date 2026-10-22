"""EvidenceVerificationAgent implementation."""

from typing import Any, Dict, List
from ..models.subagent import SubagentFinding
from ..tools.registry import execute_tool


async def run_evidence_verification(
    objective: str,
    inputs: Dict[str, Any],
    constraints: Dict[str, Any]
) -> SubagentFinding:
    """Audit empirical claims, check source provenance, and detect statistical conflicts."""
    evidence_pool = inputs.get("evidence_pool", [])
    findings = []
    
    # 1. Run conflict detection
    conflict_res = await execute_tool("evidence.find_conflicts", evidence_records=evidence_pool)
    conflicts = conflict_res.get("conflicts", [])
    conflict_count = len(conflicts)
    
    # 2. Audit empirical claims
    verified_count = 0
    for rec in evidence_pool[:5]:
        claim_text = rec.get("claim", "")
        audit_res = await execute_tool("evidence.verify_claim", claim=claim_text, source_records=evidence_pool)
        if audit_res.get("verdict") in ["SUPPORTED", "PROVISIONALLY_ACCEPTED"]:
            verified_count += 1
            
    findings.append(
        f"Evidence audit complete: Inspected {len(evidence_pool)} empirical observations. "
        f"Verified {verified_count} key claims. Detected {conflict_count} cross-source conflicts."
    )
    
    return SubagentFinding(
        agent_name="EvidenceVerificationAgent",
        objective=objective,
        findings=findings,
        evidence=[],
        calculations={
            "conflict_count": conflict_count,
            "conflicts": conflicts,
            "verified_claims_sample": verified_count
        },
        limitations=[],
        follow_up_tasks=[]
    )
