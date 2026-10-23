"""EvidenceVerificationAgent implementation with parallel tool execution."""

import asyncio
from typing import Any, Dict, List
from ..models.subagent import SubagentFinding
from ..tools.registry import execute_tool


async def run_evidence_verification(
    objective: str,
    inputs: Dict[str, Any],
    constraints: Dict[str, Any]
) -> SubagentFinding:
    """Audit empirical claims, check source provenance, and detect statistical conflicts in parallel."""
    evidence_pool = inputs.get("evidence_pool", [])
    findings = []
    
    # 1. Run conflict detection and claim verification concurrently in parallel
    conflict_task = execute_tool("evidence.find_conflicts", evidence_records=evidence_pool)
    sample_records = evidence_pool[:5]
    claim_tasks = [
        execute_tool("evidence.verify_claim", claim=rec.get("claim", ""), source_records=evidence_pool)
        for rec in sample_records
    ]
    
    gathered = await asyncio.gather(conflict_task, *claim_tasks)
    conflict_res = gathered[0]
    audit_results = gathered[1:]
    
    conflicts = conflict_res.get("conflicts", [])
    conflict_count = len(conflicts)
    
    verified_count = sum(
        1 for res in audit_results
        if res.get("verdict") in ["SUPPORTED", "PROVISIONALLY_ACCEPTED"]
    )
            
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
