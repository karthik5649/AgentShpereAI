from datetime import UTC, datetime, timedelta

import httpx

from app.agents.common import emit_agent_completed, emit_agent_error, emit_agent_started, publish_workflow_event
from app.core.config import get_settings
from app.memory.document_store import save_company, save_evidence
from app.memory.vector_store import store_company_embedding
from app.services.icp_scoring_service import score_company as icp_score_company


class ValidationAgent:
    name = "validation_agent"

    async def run(self, state: dict) -> dict:
        await emit_agent_started(state, self.name)
        validated: list[dict] = []
        icp = state.get("icp", {})
        cutoff = float(getattr(get_settings(), "ICP_QUALIFY_CUTOFF", 0.65))

        try:
            for index, company in enumerate(state.get("discovered_companies", []), start=1):
                score_res = icp_score_company(company, icp)
                score, matched, failed, unknown = score_res[:4]
                dimension_scores = getattr(score_res, "dimension_scores", {}) or company.get("dimension_scores", {})

                domain_active = await self._domain_active(company.get("domain"))
                confidence = self._assess_evidence_confidence(
                    company, domain_active=domain_active, unknown_count=len(unknown)
                )

                if score >= cutoff and domain_active:
                    icp_status = "qualified"
                elif score < 0.40 or not domain_active:
                    icp_status = "unqualified"
                else:
                    icp_status = "uncertain"

                validation_status = (
                    "validated"
                    if icp_status == "qualified"
                    else "partial"
                    if icp_status == "uncertain"
                    else "unverified"
                )

                company = {
                    **company,
                    "user_id": company.get("user_id") or state.get("user_id", "default_user"),
                    "workflow_id": company.get("workflow_id") or state.get("workflow_id", "default_wf"),
                    "icp_match_score": score,
                    "dimension_scores": dimension_scores,
                    "icp_criteria_matched": matched,
                    "icp_criteria_failed": failed,
                    "icp_criteria_unknown": unknown,
                    "icp_status": icp_status,
                    "confidence_score": confidence,
                    "validation_status": validation_status,
                }
                company_id = await save_company(company)
                company["id"] = company_id
                await store_company_embedding(company)

                # Persist evidence for field traceability
                for ev in company.get("evidence", []):
                    await save_evidence({
                        **ev,
                        "workflow_id": state["workflow_id"],
                        "entity_type": "company",
                        "entity_id": company_id,
                    })

                # Persist domain liveness evidence
                await save_evidence({
                    "workflow_id": state["workflow_id"],
                    "entity_type": "company",
                    "entity_id": company_id,
                    "field": "domain_liveness",
                    "value": domain_active,
                    "source": "http_check",
                    "source_url": f"https://{company.get('domain')}" if company.get("domain") else None,
                    "confidence": 1.0 if domain_active else 0.0,
                    "evidence_type": "api",
                })

                validated.append(company)
                await publish_workflow_event(
                    state["workflow_id"],
                    state["user_id"],
                    "progress",
                    self.name,
                    {"completed": index, "total": len(state.get("discovered_companies", []))},
                )
            if any(c.get("icp_status") == "qualified" for c in validated):
                aggregate_status = "qualified"
            elif any(c.get("icp_status") == "uncertain" for c in validated):
                aggregate_status = "uncertain"
            else:
                aggregate_status = "unqualified"

            await emit_agent_completed(
                state,
                self.name,
                {"message": f"Validation Agent stored {len(validated)} companies (aggregate: {aggregate_status})"},
            )
            return {
                "validated_companies": validated,
                "icp_status": aggregate_status,
                "agent_logs": [{"agent_name": self.name, "event_type": "companies_validated", "output_summary": len(validated)}],
            }
        except Exception as exc:
            await emit_agent_error(state, self.name, exc)
            raise

    def _assess_evidence_confidence(self, company: dict, domain_active: bool, unknown_count: int = 0) -> float:
        evidence = company.get("evidence", [])
        conflicts = company.get("conflicts", [])
        corroborated_count = sum(1 for e in evidence if "+" in str(e.get("source", "")))
        base_confidence = 0.70 + (0.05 * min(4, len(evidence))) + (0.10 * corroborated_count)
        conflict_penalty = min(0.20, len(conflicts) * 0.05)
        unknown_penalty = min(0.30, unknown_count * 0.05)
        domain_factor = 1.0 if domain_active else 0.5
        recency = self._recency_weight(company.get("updated_at"))

        final_conf = (base_confidence - conflict_penalty - unknown_penalty) * domain_factor * recency
        return round(min(0.99, max(0.20, final_conf)), 2)

    async def _domain_active(self, domain: str | None) -> bool:
        if not domain:
            return False
        if getattr(get_settings(), "MOCK_MODE", False):
            return bool("." in domain and len(domain) >= 4)
        url = domain if domain.startswith(("http://", "https://")) else f"https://{domain}"
        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                response = await client.head(url)
                if response.status_code >= 400:
                    response = await client.get(url)
            return response.status_code < 500
        except httpx.HTTPError:
            return False

    def _recency_weight(self, updated_at) -> float:
        if not updated_at:
            return 0.85
        if isinstance(updated_at, str):
            clean = updated_at.replace("Z", "+00:00")
            try:
                updated_at = datetime.fromisoformat(clean)
            except ValueError:
                return 0.85
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        return 1.0 if datetime.now(UTC) - updated_at <= timedelta(days=90) else 0.7
