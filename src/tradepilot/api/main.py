"""FastAPI web and REST API entrypoint for TradePilot AI."""

from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uuid

from ..graph.workflow import create_tradepilot_graph, create_react_supervisor_graph
from ..models.state import TradePilotState
from ..tools.registry import TOOL_REGISTRY
from ..middleware.authorization import SkillAccessMiddleware
from ..tools.meta_tools import read_skill
from ..subagents.orchestrator import supervisor, build_research_request, extract_findings, merge_evidence
from ..graph.nodes import deterministic_scoring_node, generate_report_node, validate_request_node

from pathlib import Path
from fastapi.responses import HTMLResponse
from ..middleware.tool_hooks import USAGE_TRACKER

from ..integrations import setup_copilotkit_agui

app = FastAPI(
    title="TradePilot AI API",
    version="0.2.0",
    description="Agentic Import/Export Intelligence & Regulatory Compliance Engine"
)

# Global graph instance
_graph = create_tradepilot_graph()

# Mount CopilotKit & AG-UI protocol remote endpoints
setup_copilotkit_agui(app, graph=_graph, prefix="/copilotkit")
setup_copilotkit_agui(app, graph=_graph, prefix="/ag-ui")

_INDEX_HTML_PATH = Path(__file__).parent / "index.html"
_DASHBOARD_HTML_PATH = Path(__file__).parent / "dashboard.html"
_TOKENS_CSS_PATH = Path(__file__).parent / "tokens.css"


_FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="6" fill="#1F4E46"/>
  <path d="M7 10h18M16 10v14M11 24h10" stroke="#F4F1EA" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="16" cy="17" r="2.5" fill="#D88E35"/>
</svg>"""


@app.get("/favicon.ico")
async def serve_favicon():
    """Serve TradePilot customs ledger SVG favicon."""
    from fastapi.responses import Response
    return Response(content=_FAVICON_SVG, media_type="image/svg+xml")


@app.get("/tokens.css")
@app.get("/static/tokens.css")
async def serve_tokens():
    """Serve centralized Trade Desk CSS design tokens."""
    if _TOKENS_CSS_PATH.exists():
        from fastapi.responses import Response
        return Response(content=_TOKENS_CSS_PATH.read_text(encoding="utf-8"), media_type="text/css")
    return Response(content="/* tokens not found */", status_code=404, media_type="text/css")



@app.get("/", response_class=HTMLResponse)
@app.get("/app", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the interactive TradePilot AI Copilot frontend application."""
    if _INDEX_HTML_PATH.exists():
        return HTMLResponse(content=_INDEX_HTML_PATH.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>TradePilot Frontend not found</h1>", status_code=404)


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
    thread_id: Optional[str] = Field(default=None, description="Conversational thread/session ID for multi-turn state continuity")
    query: Optional[str] = Field(default=None, description="Natural language question, trade prompt, or research instruction")
    product_query: Optional[str] = Field(default=None, description="Product name or category (optional if in query)")
    hs_code: Optional[str] = Field(default=None, description="HS 6-digit classification code")
    origin_country: Optional[str] = Field(default=None, description="Country name or ISO-3 code of exporting origin")
    candidate_destinations: Optional[List[str]] = Field(default=None, description="Target candidate markets (auto-discovered if omitted)")
    reference_years: List[int] = Field(default=[2021, 2022, 2023], description="Historical trade periods")


class ResearchResponse(BaseModel):
    run_id: str
    thread_id: Optional[str] = None
    status: str
    direct_answer: Optional[str] = None
    report_markdown: Optional[str] = None
    rankings: List[Dict[str, Any]] = []
    evidence_count: int = 0
    subagents_dispatched: List[str] = []
    query_intent: Optional[str] = None
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
    thread_id = req.thread_id or run_id
    config = {"configurable": {"thread_id": thread_id}}
    
    # If only query is provided, use it; if product_query provided, maintain backward compatibility
    effective_query = req.query or req.product_query or ""
    
    # Check if previous state exists for this thread in the LangGraph checkpointer
    existing_state = await _graph.aget_state(config)
    if existing_state and existing_state.values:
        initial_state: TradePilotState = {
            "query": effective_query,
            "current_stage": "initialized",
            "user_interrupt_needed": False,
            "user_interrupt_prompt": None,
        }
        if req.product_query:
            initial_state["product_query"] = req.product_query
        if req.origin_country:
            initial_state["origin_country"] = req.origin_country
        if req.candidate_destinations:
            initial_state["candidate_destinations"] = req.candidate_destinations
        if req.hs_code:
            initial_state["hs_code"] = req.hs_code
    else:
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
            "direct_answer": None,
            "shortlisted_destinations": [],
            "market_rankings": [],
            "final_report_markdown": None
        }
    
    try:
        final_state = await _graph.ainvoke(initial_state, config=config)
        
        if final_state.get("user_interrupt_needed"):
            return ResearchResponse(
                run_id=run_id,
                thread_id=thread_id,
                status="interrupted",
                errors=final_state.get("critical_gaps", ["User clarification required."])
            )
            
        findings = final_state.get("subagent_findings", [])
        dispatched = list(dict.fromkeys(f.get("agent_name") for f in findings if f.get("agent_name")))
        intent = final_state.get("query_intent") or ("comprehensive_feasibility" if final_state.get("market_rankings") else "trade_advisory")

        return ResearchResponse(
            run_id=run_id,
            thread_id=thread_id,
            status="completed",
            direct_answer=final_state.get("direct_answer"),
            report_markdown=final_state.get("final_report_markdown"),
            rankings=final_state.get("market_rankings", []),
            evidence_count=len(final_state.get("evidence_pool", [])),
            subagents_dispatched=dispatched,
            query_intent=intent
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")


async def execute_react_supervisor_research(req: ResearchRequest) -> Dict[str, Any]:
    """Execute dynamic ReAct supervisor loop with deterministic scoring and report finalization."""
    run_id = str(uuid.uuid4())
    thread_id = req.thread_id or run_id
    effective_query = req.query or req.product_query or ""
    
    state: TradePilotState = {
        "query": effective_query,
        "product_query": req.product_query,
        "hs_code": req.hs_code,
        "origin_country": req.origin_country,
        "candidate_destinations": req.candidate_destinations or [],
        "reference_years": req.reference_years or [2021, 2022, 2023],
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
        "direct_answer": None,
        "shortlisted_destinations": req.candidate_destinations or [],
        "market_rankings": [],
        "final_report_markdown": None
    }
    
    # 1. Pre-validation
    val_res = await validate_request_node(state)
    if val_res.get("user_interrupt_needed"):
        return {
            "run_id": run_id,
            "thread_id": thread_id,
            "status": "interrupted",
            "errors": val_res.get("critical_gaps", ["Input validation error"])
        }
        
    # 2. Dynamic model -> tool -> observation loop
    result = await supervisor.ainvoke(
        {
            "messages": [{
                "role": "user",
                "content": build_research_request(state)
            }]
        },
        config={
            "recursion_limit": 50,
            "configurable": {"thread_id": thread_id}
        }
    )
    findings = extract_findings(result)
    state["subagent_findings"] = findings
    state["evidence_pool"] = merge_evidence(findings)
    
    # Extract direct supervisor synthesized response
    direct_answer = None
    messages = result.get("messages", []) if isinstance(result, dict) else []
    if messages:
        last_msg = messages[-1]
        content = getattr(last_msg, "content", None) or (last_msg.get("content") if isinstance(last_msg, dict) else None)
        if isinstance(content, list):
            content = "\n".join(
                b.get("text", "") if isinstance(b, dict) else str(b)
                for b in content
                if not (isinstance(b, dict) and b.get("type") != "text")
            )
        if content and isinstance(content, str) and content.strip():
            direct_answer = content.strip()
    state["direct_answer"] = direct_answer
        
    # 3. Deterministic Finalization: Scoring and Report Generation
    score_update = await deterministic_scoring_node(state)
    state["market_rankings"] = score_update.get("market_rankings", [])
    
    report_update = await generate_report_node(state)
    state["final_report_markdown"] = report_update.get("final_report_markdown")
    
    findings = state["subagent_findings"]
    dispatched = list(dict.fromkeys(f.get("agent_name") for f in findings if f.get("agent_name")))
    intent = state.get("query_intent") or ("comprehensive_feasibility" if state.get("market_rankings") else "trade_advisory")

    return {
        "run_id": run_id,
        "thread_id": thread_id,
        "status": "completed",
        "direct_answer": state.get("direct_answer"),
        "report_markdown": state["final_report_markdown"],
        "rankings": state["market_rankings"],
        "evidence_count": len(state["evidence_pool"]),
        "subagents_dispatched": dispatched,
        "query_intent": intent,
        "subagent_findings_count": len(state["subagent_findings"])
    }


@app.post("/api/v1/research/react", response_model=ResearchResponse)
async def run_react_supervisor_endpoint(req: ResearchRequest):
    """Run an end-to-end export research study driven directly by the ReAct supervisor."""
    try:
        res = await execute_react_supervisor_research(req)
        return ResearchResponse(
            run_id=res["run_id"],
            thread_id=res.get("thread_id"),
            status=res["status"],
            direct_answer=res.get("direct_answer"),
            report_markdown=res.get("report_markdown"),
            rankings=res.get("rankings", []),
            evidence_count=res.get("evidence_count", 0),
            subagents_dispatched=res.get("subagents_dispatched", []),
            query_intent=res.get("query_intent"),
            errors=res.get("errors", [])
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ReAct supervisor error: {str(exc)}")
