import asyncio
import logging
from urllib.parse import urlparse

from app.agents.common import emit_agent_completed, emit_agent_error, emit_agent_started, publish_workflow_event
from app.memory.cache import acquire_lock, release_lock
from app.memory.vector_store import check_duplicate
from app.services.apollo_service import ApolloService
from app.services.crunchbase_service import CrunchbaseService
from app.services.factory import get_apollo_service, get_crunchbase_service
from app.services.icp_scoring_service import score_company as icp_score_company

logger = logging.getLogger("agentsphere.agents")


class CompanyDiscoveryAgent:
    name = "company_discovery_agent"

    def __init__(
        self,
        crunchbase_service: CrunchbaseService | None = None,
        apollo_service: ApolloService | None = None,
    ):
        self.crunchbase = crunchbase_service or get_crunchbase_service()
        self.apollo = apollo_service or get_apollo_service()

    async def run(self, state: dict) -> dict:
        await emit_agent_started(state, self.name)
        discovered: list[dict] = []
        seen_domains: set[str] = set()
        seen_names: set[str] = set()
        icp = state.get("icp", {})
        score_threshold = float(icp.get("min_icp_score") or 0.35)

        try:
            for signal in state.get("raw_signals", []):
                company_name = signal.get("company", "").strip()
                guessed_domain = (signal.get("domain") or "").strip().lower()

                # Fast in-run deduplication check before making network calls
                if guessed_domain and guessed_domain in seen_domains:
                    continue
                if company_name and company_name.lower() in seen_names:
                    continue

                lock_key = f"lock:company:{company_name.lower().replace(' ', '_')}"
                if not await acquire_lock(lock_key, timeout_seconds=30):
                    continue

                try:
                    # Multi-provider lookup: query both Crunchbase and Apollo in parallel
                    cb_task = self._safe_get_crunchbase(company_name)
                    apollo_task = self._safe_get_apollo(guessed_domain, company_name)
                    cb_details, apollo_details = await asyncio.gather(cb_task, apollo_task)

                    company = self._merge_signal_and_details(
                        signal, cb_details, apollo_details, state, guessed_domain
                    )

                    resolved_domain = (company.get("domain") or guessed_domain or "").strip().lower()
                    resolved_name = (company.get("name") or company_name).strip().lower()

                    # Check in-run and historical vector deduplication
                    if resolved_domain and resolved_domain in seen_domains:
                        continue
                    if resolved_name and resolved_name in seen_names:
                        continue
                    if resolved_domain and await check_duplicate(resolved_domain):
                        continue

                    # Score company against ICP
                    score_res = icp_score_company(company, icp)
                    score, matched, failed, unknown = score_res[:4]
                    dimension_scores = getattr(score_res, "dimension_scores", {}) or company.get("dimension_scores", {})

                    company["icp_match_score"] = score
                    company["dimension_scores"] = dimension_scores
                    company["icp_criteria_matched"] = matched
                    company["icp_criteria_failed"] = failed
                    company["icp_criteria_unknown"] = unknown

                    if score < score_threshold:
                        logger.debug("company_rejected_below_threshold: %s score=%.4f < %.4f", resolved_name, score, score_threshold)
                        continue

                    if resolved_domain:
                        seen_domains.add(resolved_domain)
                    if resolved_name:
                        seen_names.add(resolved_name)

                    discovered.append(company)
                    await publish_workflow_event(
                        state["workflow_id"],
                        state["user_id"],
                        "result",
                        self.name,
                        {"type": "company", "data": company},
                    )
                finally:
                    await release_lock(lock_key)

            await emit_agent_completed(
                state,
                self.name,
                {"message": f"Company Discovery qualified {len(discovered)} unique companies"},
            )
            return {
                "discovered_companies": discovered,
                "agent_logs": [
                    {"agent_name": self.name, "event_type": "companies_qualified", "output_summary": len(discovered)}
                ],
            }
        except Exception as exc:
            await emit_agent_error(state, self.name, exc)
            raise

    async def _safe_get_crunchbase(self, company_name: str) -> dict:
        if not company_name or not self.crunchbase:
            return {}
        try:
            return await self.crunchbase.get_company(company_name)
        except Exception as exc:
            logger.warning("Crunchbase lookup failed for '%s': %s", company_name, exc)
            return {}

    async def _safe_get_apollo(self, domain: str, company_name: str) -> dict:
        if not self.apollo:
            return {}
        try:
            return await self.apollo.enrich_organization(domain=domain, company_name=company_name)
        except Exception as exc:
            logger.warning("Apollo org enrichment failed for '%s' (%s): %s", company_name, domain, exc)
            return {}

    def _merge_signal_and_details(
        self,
        signal: dict,
        cb_details: dict,
        apollo_details: dict | None = None,
        state: dict | None = None,
        guessed_domain: str | None = None,
    ) -> dict:
        # Support calling with (signal, details, state) for backward compatibility
        if state is None:
            state = apollo_details or {}
            apollo_details = {}
        elif apollo_details is None:
            apollo_details = {}

        evidence_list: list[dict] = []
        conflicts: list[dict] = []

        # 1. Domain Resolution
        cb_website = cb_details.get("website_url") or ""
        cb_domain = self._domain_from_url(cb_website) if cb_website else None
        ap_domain = apollo_details.get("domain")
        sig_domain = guessed_domain or signal.get("domain")

        if cb_domain and ap_domain and cb_domain.lower() == ap_domain.lower():
            domain = cb_domain
            evidence_list.append({
                "field": "domain",
                "value": domain,
                "source": "crunchbase+apollo",
                "confidence": 0.98,
                "evidence_type": "verified_website",
                "notes": "Both Crunchbase and Apollo agree on domain",
            })
        elif cb_domain and ap_domain and cb_domain.lower() != ap_domain.lower():
            domain = cb_domain
            conflicts.append({
                "field": "domain",
                "sources": [
                    {"source": "crunchbase", "value": cb_domain},
                    {"source": "apollo", "value": ap_domain},
                ],
            })
            evidence_list.append({
                "field": "domain",
                "value": cb_domain,
                "source": "crunchbase",
                "confidence": 0.90,
                "evidence_type": "database",
            })
            evidence_list.append({
                "field": "domain",
                "value": ap_domain,
                "source": "apollo",
                "confidence": 0.85,
                "evidence_type": "database",
            })
        elif cb_domain:
            domain = cb_domain
            evidence_list.append({
                "field": "domain",
                "value": cb_domain,
                "source": "crunchbase",
                "confidence": 0.90,
                "evidence_type": "database",
            })
        elif ap_domain:
            domain = ap_domain
            evidence_list.append({
                "field": "domain",
                "value": ap_domain,
                "source": "apollo",
                "confidence": 0.85,
                "evidence_type": "database",
            })
        else:
            domain = sig_domain
            if domain:
                evidence_list.append({
                    "field": "domain",
                    "value": domain,
                    "source": "news_signal",
                    "confidence": 0.70,
                    "evidence_type": "inferred",
                })

        # 2. Industry Resolution
        cb_ind = cb_details.get("industry")
        ap_ind = apollo_details.get("industry")
        sig_ind = self._infer_industry_from_signal(signal, state.get("icp", {}))

        if cb_ind and ap_ind and cb_ind.lower() == ap_ind.lower():
            industry = cb_ind
            evidence_list.append({
                "field": "industry",
                "value": industry,
                "source": "crunchbase+apollo",
                "confidence": 0.98,
                "evidence_type": "verified_industry",
                "notes": "Both Crunchbase and Apollo agree on industry",
            })
        elif cb_ind and ap_ind and cb_ind.lower() != ap_ind.lower():
            industry = cb_ind
            conflicts.append({
                "field": "industry",
                "sources": [
                    {"source": "crunchbase", "value": cb_ind},
                    {"source": "apollo", "value": ap_ind},
                ],
            })
            evidence_list.append({"field": "industry", "value": cb_ind, "source": "crunchbase", "confidence": 0.90})
            evidence_list.append({"field": "industry", "value": ap_ind, "source": "apollo", "confidence": 0.85})
        elif cb_ind:
            industry = cb_ind
            evidence_list.append({"field": "industry", "value": cb_ind, "source": "crunchbase", "confidence": 0.90})
        elif ap_ind:
            industry = ap_ind
            evidence_list.append({"field": "industry", "value": ap_ind, "source": "apollo", "confidence": 0.85})
        else:
            industry = sig_ind
            if industry:
                evidence_list.append({"field": "industry", "value": industry, "source": "signal_inference", "confidence": 0.65})

        if cb_ind and sig_ind and cb_ind.lower() != sig_ind.lower():
            conflicts.append({
                "field": "industry",
                "sources": [
                    {"source": "crunchbase", "value": cb_ind},
                    {"source": "signal_inference", "value": sig_ind},
                ],
            })

        # 3. Headcount Resolution
        cb_hc = cb_details.get("headcount")
        ap_hc = apollo_details.get("headcount")

        if cb_hc is not None and ap_hc is not None:
            pct_diff = abs(cb_hc - ap_hc) / max(cb_hc, ap_hc, 1)
            if pct_diff <= 0.25:
                headcount = cb_hc
                evidence_list.append({
                    "field": "headcount",
                    "value": cb_hc,
                    "source": "crunchbase+apollo",
                    "confidence": 0.95,
                    "evidence_type": "corroborated_database",
                    "notes": f"Sources within 25%: CB={cb_hc}, Apollo={ap_hc}",
                })
            else:
                headcount = cb_hc
                conflicts.append({
                    "field": "headcount",
                    "sources": [
                        {"source": "crunchbase", "value": cb_hc},
                        {"source": "apollo", "value": ap_hc},
                    ],
                })
                evidence_list.append({"field": "headcount", "value": cb_hc, "source": "crunchbase", "confidence": 0.85})
                evidence_list.append({"field": "headcount", "value": ap_hc, "source": "apollo", "confidence": 0.80})
        elif cb_hc is not None:
            headcount = cb_hc
            evidence_list.append({"field": "headcount", "value": cb_hc, "source": "crunchbase", "confidence": 0.85})
        elif ap_hc is not None:
            headcount = ap_hc
            evidence_list.append({"field": "headcount", "value": ap_hc, "source": "apollo", "confidence": 0.80})
        else:
            headcount = None

        # 4. Funding Stage & Amount
        funding_stage = cb_details.get("funding_stage")
        funding_amount = cb_details.get("funding_amount_usd")
        if funding_stage:
            evidence_list.append({
                "field": "funding_stage",
                "value": funding_stage,
                "source": "crunchbase",
                "confidence": 0.90,
                "evidence_type": "database",
            })

        # 5. Headquarters Resolution
        cb_hq = cb_details.get("headquarters")
        ap_hq = apollo_details.get("headquarters")
        if cb_hq and ap_hq and cb_hq.lower() == ap_hq.lower():
            headquarters = cb_hq
            evidence_list.append({
                "field": "headquarters",
                "value": cb_hq,
                "source": "crunchbase+apollo",
                "confidence": 0.95,
                "notes": "Both Crunchbase and Apollo agree on headquarters",
            })
        elif cb_hq:
            headquarters = cb_hq
            evidence_list.append({"field": "headquarters", "value": cb_hq, "source": "crunchbase", "confidence": 0.90})
        elif ap_hq:
            headquarters = ap_hq
            evidence_list.append({"field": "headquarters", "value": ap_hq, "source": "apollo", "confidence": 0.85})
        else:
            headquarters = None

        # 6. Revenue Estimate
        revenue_est = cb_details.get("revenue_estimate_usd") or apollo_details.get("revenue_estimate_usd")

        # 7. Tech Stack (Union from both providers)
        cb_tech = cb_details.get("tech_stack") or []
        ap_tech = apollo_details.get("tech_stack") or []
        tech_set = set(cb_tech) | set(ap_tech)
        tech_stack = sorted(tech_set)

        # 8. Social URLs & Metadata
        linkedin_url = cb_details.get("linkedin_url") or apollo_details.get("linkedin_url")
        crunchbase_url = cb_details.get("crunchbase_url")

        display_name = cb_details.get("name") or apollo_details.get("name") or signal.get("company")

        return {
            "workflow_id": state["workflow_id"],
            "user_id": state["user_id"],
            "name": display_name,
            "domain": domain,
            "industry": industry,
            "headcount": headcount,
            "funding_stage": funding_stage,
            "funding_amount_usd": funding_amount,
            "revenue_estimate_usd": revenue_est,
            "headquarters": headquarters,
            "linkedin_url": linkedin_url,
            "crunchbase_url": crunchbase_url,
            "tech_stack": tech_stack,
            "triggers_matched": [signal.get("trigger_type")] if signal.get("trigger_type") else [],
            "source_signal": signal,
            "description": cb_details.get("description") or signal.get("signal"),
            "updated_at": cb_details.get("updated_at"),
            "evidence": evidence_list,
            "conflicts": conflicts,
        }

    def _infer_industry_from_signal(self, signal: dict, icp: dict) -> str | None:
        text = f"{signal.get('signal', '')} {signal.get('company', '')}".lower()
        for industry in icp.get("industry", []):
            if industry.lower() in text:
                return industry
        return None

    def score_company(self, company: dict, icp: dict) -> tuple[float, list[str]]:
        score_res = icp_score_company(company, icp)
        return score_res[0], score_res[1]

    def _domain_from_url(self, url: str) -> str | None:
        netloc = urlparse(url).netloc.lower()
        return netloc.removeprefix("www.") if netloc else None
