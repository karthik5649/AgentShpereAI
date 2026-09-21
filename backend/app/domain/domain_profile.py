from typing import Any, Optional
from pydantic import BaseModel, Field


class DomainProfile(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    icp_dimensions: list[str] = Field(default_factory=list)
    default_weights: dict[str, float] = Field(default_factory=dict)
    default_cutoff: float = 0.65
    default_triggers: list[str] = Field(default_factory=list)
    persona_vocabulary: list[dict[str, Any]] = Field(default_factory=list)


DEFAULT_DOMAIN_PROFILES = [
    DomainProfile(
        id="b2b_saas",
        name="B2B SaaS",
        description="Standard profile for B2B Software-as-a-Service and Cloud platforms.",
        icp_dimensions=["industry", "headcount", "funding_stage", "geography", "revenue", "tech_stack"],
        default_weights={
            "industry": 0.25,
            "headcount": 0.20,
            "funding_stage": 0.20,
            "geography": 0.15,
            "revenue": 0.10,
            "tech_stack": 0.10,
        },
        default_cutoff=0.65,
        default_triggers=["funding_round", "hiring_expansion", "leadership_change", "product_launch"],
        persona_vocabulary=[
            {"title": "VP Engineering", "department": "Engineering", "seniority": "VP"},
            {"title": "Chief Technology Officer", "department": "Executive", "seniority": "C-Level"},
            {"title": "Head of Product", "department": "Product", "seniority": "Director"},
        ],
    ),
    DomainProfile(
        id="staffing_recruiting",
        name="Staffing & Recruiting",
        description="Profile tailored for Staffing agencies, Talent Acquisition, and Executive Search firms.",
        icp_dimensions=["industry", "headcount", "geography", "job_openings", "revenue"],
        default_weights={
            "industry": 0.30,
            "headcount": 0.25,
            "geography": 0.20,
            "revenue": 0.15,
            "tech_stack": 0.10,
        },
        default_cutoff=0.60,
        default_triggers=["hiring_expansion", "executive_appointment", "office_opening"],
        persona_vocabulary=[
            {"title": "Head of Talent Acquisition", "department": "HR", "seniority": "Director"},
            {"title": "Chief People Officer", "department": "Executive", "seniority": "C-Level"},
            {"title": "VP Human Resources", "department": "HR", "seniority": "VP"},
        ],
    ),
]
