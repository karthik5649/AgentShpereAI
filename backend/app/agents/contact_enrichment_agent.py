from __future__ import annotations

import asyncio
import hashlib
import logging

from app.agents.common import emit_agent_completed, emit_agent_error, emit_agent_started, publish_workflow_event
from app.memory.cache import get_cached, set_cached
from app.memory.document_store import save_contact, save_evidence
from app.services.apollo_service import ApolloService
from app.services.coresignal_service import CoresignalService, normalize_linkedin_url
from app.services.factory import get_apollo_service, get_coresignal_service, get_hunter_service
from app.services.hunter_service import HunterService

logger = logging.getLogger("agentsphere.agents")

# News / aggregator domains — don't bother enriching contacts from these
_SKIP_DOMAINS = frozenset({
    "thesaasnews.com", "saasrise.com", "news.crunchbase.com", "crunchbase.com",
    "techinasia.com", "inc42.com", "thenextweb.com", "tech.eu", "osborneclarke.com",
    "ycombinator.com", "highalpha.com", "team4.agency", "b2b.economictimes.indiatimes.com",
    "reddit.com", "x.com", "twitter.com", "youtube.com", "medium.com",
    "techcrunch.com", "reuters.com", "bloomberg.com", "forbes.com",
})

# Maximum number of contacts to enrich per workflow run (to prevent multi-minute hangs)
MAX_CONTACTS_TO_ENRICH = 10


class ContactEnrichmentAgent:
    name = "contact_enrichment_agent"

    def __init__(
        self,
        hunter_service: HunterService | None = None,
        apollo_service: ApolloService | None = None,
        coresignal_service: CoresignalService | None = None,
    ):
        self.hunter = hunter_service or get_hunter_service()
        self.apollo = apollo_service or get_apollo_service()
        self.coresignal = coresignal_service or get_coresignal_service()

    async def run(self, state: dict) -> dict:
        await emit_agent_started(state, self.name)
        enriched: list[dict] = []
        try:
            all_decision_makers = state.get("decision_makers", [])

            # Filter out contacts from news/media sites before enrichment
            valid_decision_makers = [
                dm for dm in all_decision_makers
                if dm.get("domain") not in _SKIP_DOMAINS
                and not any(skip in (dm.get("domain") or "") for skip in ["news", "crunchbase", "reddit", "thesaas"])
            ]

            # Cap at MAX_CONTACTS_TO_ENRICH to prevent run-away API calls
            decision_makers_to_enrich = valid_decision_makers[:MAX_CONTACTS_TO_ENRICH]

            await publish_workflow_event(
                state["workflow_id"],
                state["user_id"],
                "progress",
                self.name,
                {"message": f"Enriching {len(decision_makers_to_enrich)} contacts (capped at {MAX_CONTACTS_TO_ENRICH})"},
            )

            for decision_maker in decision_makers_to_enrich:
                try:
                    contact = await self._enrich_one(decision_maker)
                    contact_id = await save_contact(contact)
                    contact["id"] = contact_id

                    # Persist contact evidence safely
                    if contact.get("email"):
                        await save_evidence({
                            "workflow_id": state["workflow_id"],
                            "entity_type": "contact",
                            "entity_id": contact_id,
                            "field": "email",
                            "value": contact["email"],
                            "source": contact.get("email_source") or "hunter",
                            "confidence": contact.get("email_confidence") or 0.90,
                            "evidence_type": "api",
                            "notes": f"Email verified via {contact.get('email_source', 'unknown')}",
                        })
                    if contact.get("phone"):
                        await save_evidence({
                            "workflow_id": state["workflow_id"],
                            "entity_type": "contact",
                            "entity_id": contact_id,
                            "field": "phone",
                            "value": contact["phone"],
                            "source": contact.get("phone_source") or "apollo",
                            "confidence": 0.85,
                            "evidence_type": "api",
                            "notes": f"Phone verified via {contact.get('phone_source', 'apollo')}",
                        })
                    if contact.get("linkedin_url"):
                        clean_linkedin = normalize_linkedin_url(contact["linkedin_url"])
                        if clean_linkedin:
                            await save_evidence({
                                "workflow_id": state["workflow_id"],
                                "entity_type": "contact",
                                "entity_id": contact_id,
                                "field": "linkedin_url",
                                "value": clean_linkedin,
                                "source": contact.get("linkedin_source") or "linkedin_search",
                                "source_url": clean_linkedin,
                                "confidence": 0.95,
                                "evidence_type": "social",
                            })

                    enriched.append(contact)
                    await publish_workflow_event(
                        state["workflow_id"],
                        state["user_id"],
                        "result",
                        self.name,
                        {"type": "contact", "data": contact},
                    )
                except Exception as exc:
                    logger.warning(
                        "ContactEnrichmentAgent: error processing contact %s: %s",
                        decision_maker.get("name"),
                        exc,
                    )

            await emit_agent_completed(
                state,
                self.name,
                {"message": f"Contact Enrichment Agent enriched {len(enriched)} contacts"},
            )
            return {
                "enriched_contacts": enriched,
                "agent_logs": [{"agent_name": self.name, "event_type": "contacts_enriched", "output_summary": len(enriched)}],
            }
        except Exception as exc:
            await emit_agent_error(state, self.name, exc)
            raise

    async def _enrich_one(self, decision_maker: dict) -> dict:
        """Enrich a single contact combining Hunter + Apollo + Coresignal with fallback."""
        name_hash = hashlib.sha256(str(decision_maker.get("name", "")).encode("utf-8")).hexdigest()
        cache_key = f"cache:contact:{decision_maker.get('domain')}:{name_hash}"

        try:
            cached = await get_cached(cache_key)
            if isinstance(cached, dict):
                return {**decision_maker, **cached, "approval_status": "pending"}
        except Exception as cache_exc:
            logger.debug("Cache read bypass for contact enrichment: %s", cache_exc)

        first, last = self._split_name(decision_maker.get("name", ""))

        # 1. Hunter email search with timeout
        try:
            email = await asyncio.wait_for(
                self.hunter.find_email(decision_maker.get("domain"), first, last),
                timeout=12.0,
            )
        except (asyncio.TimeoutError, Exception):
            email = {"email": None, "confidence": 0}

        # 2. Apollo contact match (phone, LinkedIn, and fallback email)
        try:
            apollo = await self.apollo.find_contact(
                decision_maker.get("name", ""),
                decision_maker.get("company", ""),
                decision_maker.get("linkedin_url"),
            )
        except Exception as exc:
            logger.debug("Apollo find_contact skipped/failed: %s", exc)
            apollo = {}

        # 3. Coresignal contact match (cross-verifies title, LinkedIn profile, employment history)
        coresignal = {}
        try:
            if self.coresignal:
                coresignal = await self.coresignal.find_contact(
                    decision_maker.get("name", ""),
                    decision_maker.get("company", ""),
                    decision_maker.get("linkedin_url"),
                )
        except Exception as exc:
            logger.debug("Coresignal find_contact skipped/failed: %s", exc)
            coresignal = {}

        hunter_email = email.get("email") if isinstance(email, dict) else None
        hunter_conf = (email.get("confidence") or 0) if isinstance(email, dict) else 0
        apollo_email = apollo.get("email") or decision_maker.get("email")

        # Combine Hunter + Apollo email
        if hunter_email and hunter_conf >= 70:
            final_email = hunter_email
            final_email_conf = hunter_conf / 100.0 if hunter_conf > 1 else hunter_conf
            email_source = "hunter"
            if apollo_email and hunter_email.lower() == apollo_email.lower():
                email_source = "hunter+apollo"
                final_email_conf = 0.98
        elif apollo_email:
            final_email = apollo_email
            final_email_conf = 0.88
            email_source = "apollo"
        elif hunter_email:
            final_email = hunter_email
            final_email_conf = hunter_conf / 100.0 if hunter_conf > 1 else hunter_conf
            email_source = "hunter"
        else:
            final_email = None
            final_email_conf = None
            email_source = None

        final_phone = apollo.get("phone") or decision_maker.get("phone")
        phone_source = "apollo" if final_phone else None

        # Resolve verified LinkedIn URL across Apollo, Coresignal, and initial discovery
        final_linkedin = (
            normalize_linkedin_url(apollo.get("linkedin_url"))
            or normalize_linkedin_url(coresignal.get("linkedin_url"))
            or normalize_linkedin_url(decision_maker.get("linkedin_url"))
        )

        linkedin_source = (
            "apollo" if apollo.get("linkedin_url")
            else "coresignal" if coresignal.get("linkedin_url")
            else "linkedin_search" if decision_maker.get("linkedin_url")
            else None
        )

        employment_history = apollo.get("employment_history") or coresignal.get("employment_history") or []

        contact = {
            **decision_maker,
            "email": final_email,
            "email_confidence": final_email_conf,
            "email_source": email_source,
            "phone": final_phone,
            "phone_source": phone_source,
            "linkedin_url": final_linkedin,
            "linkedin_source": linkedin_source,
            "employment_history": employment_history,
            "approval_status": "pending",
        }

        try:
            await set_cached(
                cache_key,
                {
                    "email": contact.get("email"),
                    "email_confidence": contact.get("email_confidence"),
                    "email_source": contact.get("email_source"),
                    "phone": contact.get("phone"),
                    "phone_source": contact.get("phone_source"),
                    "linkedin_url": contact.get("linkedin_url"),
                    "linkedin_source": contact.get("linkedin_source"),
                    "employment_history": contact.get("employment_history", []),
                },
                43200,
            )
        except Exception as cache_exc:
            logger.debug("Cache write bypass for contact enrichment: %s", cache_exc)

        return contact

    def _split_name(self, name: str) -> tuple[str, str]:
        parts = [part for part in name.strip().split(" ") if part]
        if not parts:
            return "", ""
        if len(parts) == 1:
            return parts[0], ""
        return parts[0], parts[-1]
