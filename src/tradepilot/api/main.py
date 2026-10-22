"""FastAPI web and REST API entrypoint for TradePilot AI."""

from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uuid

from ..graph.workflow import create_tradepilot_graph
from ..models.state import TradePilotState
from ..tools.registry import TOOL_REGISTRY
from ..middleware.authorization import SkillAccessMiddleware
from ..tools.meta_tools import read_skill

app = FastAPI(
    title="TradePilot AI API",
    version="0.1.0",
    description="Agentic Import/Export Intelligence & Regulatory Compliance Engine"
)

# Global graph instance
_graph = create_tradepilot_graph()


class ResearchRequest(BaseModel):
    product_query: str = Field(description="Product name or query (e.g. 'Specialty Roasted Coffee')")
    hs_code: Optional[str] = Field(default="090121", description="HS 6-digit classification code")
    origin_country: str = Field(default="IND", description="ISO-3 code of exporting origin")
    candidate_destinations: List[str] = Field(default=["DEU", "USA"], description="Target candidate markets")
    reference_years: List[int] = Field(default=[2021, 2022, 2023], description="Historical trade periods")


class ResearchResponse(BaseModel):
    run_id: str
    status: str
    report_markdown: Optional[str] = None
    rankings: List[Dict[str, Any]] = []
    evidence_count: int = 0
    errors: List[str] = []


@app.get("/api/v1/health")
async def health_check():
    """Health status and registered components."""
    return {
        "status": "healthy",
        "registered_tools_count": len(TOOL_REGISTRY),
        "available_tools": list(TOOL_REGISTRY.keys()),
        "approved_skills": SkillAccessMiddleware.APPROVED_SKILLS
    }


@app.get("/api/v1/skills")
async def list_skills():
    """List approved skills with their descriptions."""
    skills = []
    for s_name in SkillAccessMiddleware.APPROVED_SKILLS:
        res = read_skill(s_name)
        skills.append({
            "name": s_name,
            "status": res.get("status"),
            "preview": res.get("instructions", "")[:200] + "..."
        })
    return {"skills": skills}


@app.post("/api/v1/research", response_model=ResearchResponse)
async def run_export_research(req: ResearchRequest):
    """Run an end-to-end export feasibility study via LangGraph."""
    run_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": run_id}}
    
    initial_state: TradePilotState = {
        "product_query": req.product_query,
        "hs_code": req.hs_code,
        "origin_country": req.origin_country,
        "candidate_destinations": req.candidate_destinations,
        "reference_years": req.reference_years,
        "active_skills": [],
        "execution_plan": [],
        "current_stage": "initialized",
        "follow_up_count": 0,
        "critical_gaps": [],
        "user_interrupt_needed": False,
        "user_interrupt_prompt": None,
        "evidence_pool": [],
        "subagent_findings": [],
        "shortlisted_destinations": [],
        "market_rankings": [],
        "final_report_markdown": None
    }
    
    try:
        final_state = await _graph.ainvoke(initial_state, config=config)
        
        if final_state.get("user_interrupt_needed"):
            return ResearchResponse(
                run_id=run_id,
                status="interrupted",
                errors=final_state.get("critical_gaps", ["User clarification required."])
            )
            
        return ResearchResponse(
            run_id=run_id,
            status="completed",
            report_markdown=final_state.get("final_report_markdown"),
            rankings=final_state.get("market_rankings", []),
            evidence_count=len(final_state.get("evidence_pool", []))
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")
