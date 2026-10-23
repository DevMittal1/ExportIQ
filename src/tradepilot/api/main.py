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

from pathlib import Path
from fastapi.responses import HTMLResponse
from ..middleware.tool_hooks import USAGE_TRACKER

app = FastAPI(
    title="TradePilot AI API",
    version="0.2.0",
    description="Agentic Import/Export Intelligence & Regulatory Compliance Engine"
)

# Global graph instance
_graph = create_tradepilot_graph()

_DASHBOARD_HTML_PATH = Path(__file__).parent / "dashboard.html"


class BudgetUpdateRequest(BaseModel):
    tool_name: str = Field(..., description="Target tool name to cap or update")
    max_calls: int = Field(..., description="Maximum allowed invocations (0 or negative to remove)")


@app.get("/dashboard", response_class=HTMLResponse)
@app.get("/admin", response_class=HTMLResponse)
async def serve_dashboard():
    """Serve the interactive API usage monitoring and budget control dashboard."""
    if _DASHBOARD_HTML_PATH.exists():
        return HTMLResponse(content=_DASHBOARD_HTML_PATH.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Dashboard UI not found</h1>", status_code=404)


@app.get("/api/v1/metrics/api-usage")
async def get_api_usage_metrics():
    """Retrieve live API tool usage counts, latencies, and budget controls from persistent DB."""
    return USAGE_TRACKER.get_summary()


@app.get("/api/v1/metrics/logs")
async def get_tool_execution_logs(
    limit: int = 50,
    offset: int = 0,
    tool_name: Optional[str] = None,
    status: Optional[str] = None
):
    """Retrieve historical tool invocation logs stored in persistent SQLite."""
    logs = USAGE_TRACKER.get_logs(limit=limit, offset=offset, tool_name=tool_name, status=status)
    return {"logs": logs, "count": len(logs), "offset": offset, "limit": limit}


@app.post("/api/v1/metrics/budget")
async def update_tool_budget(req: BudgetUpdateRequest):
    """Set or update quota budget cap for a specific tool in memory and persistent SQLite."""
    if req.max_calls <= 0:
        USAGE_TRACKER.remove_budget(req.tool_name)
        return {"status": "success", "message": f"Budget limit removed for '{req.tool_name}'"}
    USAGE_TRACKER.set_budget(req.tool_name, req.max_calls)
    return {
        "status": "success",
        "message": f"Budget limit set to {req.max_calls} for '{req.tool_name}'",
        "tool_name": req.tool_name,
        "max_calls": req.max_calls
    }


@app.post("/api/v1/metrics/reset")
async def reset_metrics():
    """Purge execution logs and reset metrics and budgets."""
    USAGE_TRACKER.reset()
    return {"status": "success", "message": "All execution logs and metrics reset successfully."}



class ResearchRequest(BaseModel):
    query: Optional[str] = Field(default=None, description="Natural language question, trade prompt, or research instruction")
    product_query: Optional[str] = Field(default=None, description="Product name or category (optional if in query)")
    hs_code: Optional[str] = Field(default=None, description="HS 6-digit classification code")
    origin_country: Optional[str] = Field(default=None, description="Country name or ISO-3 code of exporting origin")
    candidate_destinations: Optional[List[str]] = Field(default=None, description="Target candidate markets (auto-discovered if omitted)")
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
    """Run an end-to-end export study, market discovery, or trade advisory inquiry."""
    run_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": run_id}}
    
    # If only query is provided, use it; if product_query provided, maintain backward compatibility
    effective_query = req.query or req.product_query or ""
    
    initial_state: TradePilotState = {
        "query": effective_query,
        "product_query": req.product_query,
        "hs_code": req.hs_code,
        "origin_country": req.origin_country,
        "candidate_destinations": req.candidate_destinations or [],
        "reference_years": req.reference_years,
        "query_intent": None,
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
