from typing import Any, Type
from uuid import uuid4

from pydantic import BaseModel, Field

from app.agents.company_discovery_agent import CompanyDiscoveryAgent
from app.agents.contact_enrichment_agent import ContactEnrichmentAgent
from app.agents.decision_maker_agent import DecisionMakerAgent
from app.agents.human_approval_agent import HumanApprovalAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.search_agent import SearchAgent
from app.agents.summary_agent import SummaryAgent
from app.agents.validation_agent import ValidationAgent


# --- Pydantic Schemas for Agent Input / Output ---

class PlannerInputSchema(BaseModel):
    icp: dict[str, Any] = Field(default_factory=dict)
    personas: list[dict[str, Any]] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)


class PlannerOutputSchema(BaseModel):
    execution_plan: dict[str, Any]
    total_tokens: int = 0
    total_cost_usd: float = 0.0


class SearchInputSchema(BaseModel):
    icp: dict[str, Any] = Field(default_factory=dict)
    triggers: list[str] = Field(default_factory=list)
    execution_plan: dict[str, Any] | None = None


class SearchOutputSchema(BaseModel):
    raw_signals: list[dict[str, Any]]


class CompanyDiscoveryInputSchema(BaseModel):
    icp: dict[str, Any] = Field(default_factory=dict)
    raw_signals: list[dict[str, Any]] = Field(default_factory=list)


class CompanyDiscoveryOutputSchema(BaseModel):
    discovered_companies: list[dict[str, Any]]


class ValidationInputSchema(BaseModel):
    icp: dict[str, Any] = Field(default_factory=dict)
    discovered_companies: list[dict[str, Any]] = Field(default_factory=list)


class ValidationOutputSchema(BaseModel):
    validated_companies: list[dict[str, Any]]
    icp_status: str | None = None


class DecisionMakerInputSchema(BaseModel):
    validated_companies: list[dict[str, Any]] = Field(default_factory=list)
    personas: list[dict[str, Any]] = Field(default_factory=list)


class DecisionMakerOutputSchema(BaseModel):
    decision_makers: list[dict[str, Any]]


class ContactEnrichmentInputSchema(BaseModel):
    decision_makers: list[dict[str, Any]] = Field(default_factory=list)


class ContactEnrichmentOutputSchema(BaseModel):
    enriched_contacts: list[dict[str, Any]]


class SummaryInputSchema(BaseModel):
    validated_companies: list[dict[str, Any]] = Field(default_factory=list)
    enriched_contacts: list[dict[str, Any]] = Field(default_factory=list)


class SummaryOutputSchema(BaseModel):
    summary_report: dict[str, Any]


class HumanApprovalInputSchema(BaseModel):
    enriched_contacts: list[dict[str, Any]] = Field(default_factory=list)
    summary_report: dict[str, Any] | None = None


class HumanApprovalOutputSchema(BaseModel):
    approval_status: str


# Attach input_schema and output_schema class attributes to agent classes
PlannerAgent.input_schema = PlannerInputSchema
PlannerAgent.output_schema = PlannerOutputSchema

SearchAgent.input_schema = SearchInputSchema
SearchAgent.output_schema = SearchOutputSchema

CompanyDiscoveryAgent.input_schema = CompanyDiscoveryInputSchema
CompanyDiscoveryAgent.output_schema = CompanyDiscoveryOutputSchema

ValidationAgent.input_schema = ValidationInputSchema
ValidationAgent.output_schema = ValidationOutputSchema

DecisionMakerAgent.input_schema = DecisionMakerInputSchema
DecisionMakerAgent.output_schema = DecisionMakerOutputSchema

ContactEnrichmentAgent.input_schema = ContactEnrichmentInputSchema
ContactEnrichmentAgent.output_schema = ContactEnrichmentOutputSchema

SummaryAgent.input_schema = SummaryInputSchema
SummaryAgent.output_schema = SummaryOutputSchema

HumanApprovalAgent.input_schema = HumanApprovalInputSchema
HumanApprovalAgent.output_schema = HumanApprovalOutputSchema


FUNCTIONAL_AGENT_REGISTRY: dict[str, Type] = {
    "planner_agent": PlannerAgent,
    "search_agent": SearchAgent,
    "company_discovery_agent": CompanyDiscoveryAgent,
    "validation_agent": ValidationAgent,
    "decision_maker_agent": DecisionMakerAgent,
    "contact_enrichment_agent": ContactEnrichmentAgent,
    "summary_agent": SummaryAgent,
    "human_approval_agent": HumanApprovalAgent,
}


def build_minimal_agent_state(agent_id: str, payload: dict[str, Any], user_id: str = "test_user") -> dict[str, Any]:
    """Construct a minimal valid AgentState for isolated agent execution."""
    uid = f"test_{uuid4().hex[:8]}"
    state: dict[str, Any] = {
        "workflow_id": f"wf_{uid}",
        "session_id": f"sess_{uid}",
        "user_id": user_id,
        "icp": payload.get("icp", {}),
        "personas": payload.get("personas", []),
        "triggers": payload.get("triggers", []),
        "execution_plan": payload.get("execution_plan"),
        "raw_signals": payload.get("raw_signals", []),
        "discovered_companies": payload.get("discovered_companies", []),
        "validated_companies": payload.get("validated_companies", []),
        "decision_makers": payload.get("decision_makers", []),
        "enriched_contacts": payload.get("enriched_contacts", []),
        "summary_report": payload.get("summary_report"),
        "approval_status": payload.get("approval_status"),
        "agent_logs": [],
        "total_tokens": 0,
        "total_cost_usd": 0.0,
        "errors": [],
    }
    # Update with any additional keys provided in payload
    for k, v in payload.items():
        state[k] = v
    return state
