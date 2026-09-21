from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

EvidenceType = Literal[
    "official_website",
    "news",
    "database",
    "social",
    "third_party",
    "api",
    "inferred",
    "llm",
]


class Evidence(BaseModel):
    id: str = Field(default_factory=lambda: f"ev_{uuid4().hex}")
    workflow_id: str
    entity_type: str = "company"  # "company" | "contact"
    entity_id: str
    field: str
    value: Any
    source: str
    source_url: str | None = None
    retrieved_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    confidence: float = 1.0
    evidence_type: EvidenceType = "database"


class EvidenceListResponse(BaseModel):
    company_id: str
    total: int
    evidence: list[Evidence]
