"""TradeAdvisoryAgent implementation for general and strategic trade inquiries."""

from typing import Any, Dict, List
from ..models.subagent import SubagentFinding
from ..tools.registry import execute_tool


# Knowledge base of core trade advisory concepts
TRADE_KNOWLEDGE_BASE: Dict[str, Dict[str, str]] = {
    "incoterms": {
        "summary": "Incoterms (International Commercial Terms) 2020 define responsibilities, costs, and risks between buyers and sellers.",
        "details": (
            "• **EXW (Ex Works):** Maximum buyer risk; buyer handles all transport and customs clearance from seller door.\n"
            "• **FOB (Free On Board):** Maritime standard; seller clears export and delivers goods past ship rail at origin port; buyer covers ocean freight and destination risks.\n"
            "• **CIF (Cost, Insurance & Freight):** Seller covers ocean freight and minimum marine cargo insurance to destination port; risk transfers when loaded on vessel.\n"
            "• **DAP (Delivered at Place):** Seller delivers to named destination terminal/facility ready for unloading; buyer pays import duties and local clearance.\n"
            "• **DDP (Delivered Duty Paid):** Maximum seller risk; seller covers all logistics, duties, taxes, and destination customs clearance."
        )
    },
    "customs_and_docs": {
        "summary": "Standard international commercial documentation required across global customs agencies.",
        "details": (
            "• **Commercial Invoice & Packing List:** Detailing HS codes, unit prices, net/gross weights, and Incoterm.\n"
            "• **Bill of Lading (B/L) / Air Waybill (AWB):** Contract of carriage and document of title.\n"
            "• **Certificate of Origin (CoO):** Non-preferential or preferential (to claim FTA reduced duties).\n"
            "• **Inspection / Phytosanitary Certificates:** Required for agricultural, food, chemicals, and veterinary goods."
        )
    },
    "trade_finance": {
        "summary": "Risk mitigation instruments in international B2B commerce.",
        "details": (
            "• **Letter of Credit (LC):** Bank guarantee guaranteeing payment upon compliant presentation of shipping documents.\n"
            "• **Export Factoring:** Selling foreign accounts receivable at a discount for immediate cash flow.\n"
            "• **Export Credit Insurance:** Protecting exporters against foreign buyer commercial insolvency and political risk."
        )
    }
}


async def run_trade_advisory(
    objective: str,
    inputs: Dict[str, Any],
    constraints: Dict[str, Any]
) -> SubagentFinding:
    """Provide structured domain guidance for trade queries, logistics, or advisory."""
    query = inputs.get("query", objective).lower()
    findings = []
    calculations = {}
    
    # 1. Match relevant trade concepts
    matched_topics = []
    if any(k in query for k in ["incoterm", "fob", "cif", "dap", "ddp", "exw", "shipping terms"]):
        matched_topics.append("incoterms")
    if any(k in query for k in ["document", "customs", "clearance", "certificate", "invoice", "origin", "carnet"]):
        matched_topics.append("customs_and_docs")
    if any(k in query for k in ["finance", "letter of credit", "lc", "factoring", "payment", "bank"]):
        matched_topics.append("trade_finance")
        
    # Default to Incoterms and customs if none specifically triggered
    if not matched_topics:
        matched_topics = ["incoterms", "customs_and_docs"]
        
    for topic in matched_topics:
        entry = TRADE_KNOWLEDGE_BASE.get(topic)
        if entry:
            findings.append(f"**{topic.replace('_', ' ').title()}:** {entry['summary']}\n{entry['details']}")
            calculations[topic] = entry
            
    findings.append(
        "Trade Advisory Guideline: Always ensure contract clauses align with chosen Incoterms 2020 rules and verify local customs documentation at origin and destination."
    )
    
    return SubagentFinding(
        agent_name="TradeAdvisoryAgent",
        objective=objective,
        findings=findings,
        evidence=[],
        calculations=calculations,
        limitations=["Advisory provides general trade principles; consult licensed customs brokers for country-specific filings."],
        follow_up_tasks=[]
    )
