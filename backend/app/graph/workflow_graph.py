from langgraph.graph import END, StateGraph

from app.graph.nodes import (
    approval_node,
    company_discovery_node,
    decision_maker_node,
    enrichment_node,
    planner_node,
    search_node,
    summary_node,
    validation_node,
)
from app.graph.state import AgentState


def route_after_validation(state: AgentState) -> str:
    """Route after validation based on aggregate ICP status.

    - qualified: proceed to decision_maker -> enrichment
    - uncertain: proceed to decision_maker, but companies flagged for review
    - unqualified: skip enrichment and proceed directly to summary
    """
    icp_status = state.get("icp_status")
    if icp_status in {"qualified", "uncertain", "unqualified"}:
        return icp_status

    validated = state.get("validated_companies", [])
    if not validated:
        return "unqualified"

    statuses = [c.get("icp_status") for c in validated]
    if any(s == "qualified" for s in statuses):
        return "qualified"
    if any(s == "uncertain" for s in statuses):
        return "uncertain"
    return "unqualified"


def build_workflow_graph():
    graph = StateGraph(AgentState)

    graph.add_node("planner", planner_node)
    graph.add_node("search", search_node)
    graph.add_node("company_discovery", company_discovery_node)
    graph.add_node("validation", validation_node)
    graph.add_node("decision_maker", decision_maker_node)
    graph.add_node("enrichment", enrichment_node)
    graph.add_node("summary", summary_node)
    graph.add_node("approval", approval_node)

    graph.set_entry_point("planner")

    graph.add_edge("planner", "search")
    graph.add_edge("search", "company_discovery")
    graph.add_edge("company_discovery", "validation")

    graph.add_conditional_edges(
        "validation",
        route_after_validation,
        {
            "qualified": "decision_maker",
            "uncertain": "decision_maker",
            "unqualified": "summary",
        },
    )

    graph.add_edge("decision_maker", "enrichment")
    graph.add_edge("enrichment", "summary")
    graph.add_edge("summary", "approval")
    graph.add_edge("approval", END)

    return graph.compile()
