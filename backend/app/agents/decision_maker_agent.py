import logging

from app.agents.common import emit_agent_completed, emit_agent_error, emit_agent_started, publish_workflow_event
from app.services.apollo_service import ApolloService
from app.services.factory import get_apollo_service
from app.tools.linkedin_tool import LinkedInTool, _NEWS_DOMAINS

logger = logging.getLogger("agentsphere.agents")

SENIORITY_RANK = {
    "c-suite": 5,
    "vp": 4,
    "director": 3,
    "manager": 2,
    "individual contributor": 1,
}


class DecisionMakerAgent:
    name = "decision_maker_agent"

    def __init__(
        self,
        apollo_service: ApolloService | None = None,
        linkedin_tool: LinkedInTool | None = None,
    ):
        self.apollo = apollo_service or get_apollo_service()
        self.linkedin = linkedin_tool or LinkedInTool()

    async def run(self, state: dict) -> dict:
        await emit_agent_started(state, self.name)
        decision_makers: list[dict] = []
        try:
            for company in state.get("validated_companies", []):
                domain = company.get("domain", "")
                if domain in _NEWS_DOMAINS or any(nd in domain for nd in [
                    "news", "techcrunch", "crunchbase", "reddit", "medium",
                    "twitter", "youtube", "facebook", "saasrise", "thesaasnews",
                ]):
                    continue

                candidates: list[dict] = []
                c_name = company.get("name", "")

                for persona in state.get("personas", []):
                    titles = persona.get("titles", [])
                    people = []
                    search_path = "apollo_people_search"

                    # 1. Try Apollo People Search endpoint first
                    try:
                        if self.apollo:
                            people = await self.apollo.search_people(c_name, domain, titles)
                    except Exception as exc:
                        logger.warning("Apollo search_people error for '%s': %s", c_name, exc)
                        people = []

                    # 2. Fall back to Serper LinkedIn search if Apollo returns nothing
                    if not people:
                        search_path = "serper_linkedin_fallback"
                        try:
                            people = await self.linkedin.search_people(c_name, titles)
                        except Exception as exc:
                            logger.warning("LinkedIn fallback search error for '%s': %s", c_name, exc)
                            people = []

                    logger.debug(
                        "decision_maker_search: company=%s persona=%s source=%s results=%d",
                        c_name,
                        persona.get("name"),
                        search_path,
                        len(people),
                    )

                    for person in people:
                        title = person.get("title", "")
                        if not self._matches_persona(title, persona):
                            continue
                        seniority = self._seniority(title)
                        candidates.append(
                            {
                                "workflow_id": state["workflow_id"],
                                "user_id": state["user_id"],
                                "company_id": company.get("id"),
                                "company": c_name,
                                "domain": domain,
                                "name": person.get("name"),
                                "title": title,
                                "seniority": seniority,
                                "department": self._department(title),
                                "linkedin_url": person.get("linkedin_url"),
                                "email": person.get("email"),
                                "phone": person.get("phone"),
                                "discovery_source": search_path,
                                "persona_matched": persona.get("name"),
                                "persona_priority": persona.get("priority", 1),
                            }
                        )

                ranked = sorted(
                    candidates,
                    key=lambda item: (-SENIORITY_RANK.get(item.get("seniority", ""), 0), item.get("persona_priority", 1)),
                )[:3]
                decision_makers.extend(ranked)

                for contact in ranked:
                    await publish_workflow_event(
                        state["workflow_id"],
                        state["user_id"],
                        "result",
                        self.name,
                        {"type": "decision_maker", "data": contact},
                    )

            await emit_agent_completed(
                state,
                self.name,
                {"message": f"Decision Maker Agent found {len(decision_makers)} contacts"},
            )
            return {
                "decision_makers": decision_makers,
                "agent_logs": [
                    {"agent_name": self.name, "event_type": "decision_makers_found", "output_summary": len(decision_makers)}
                ],
            }
        except Exception as exc:
            await emit_agent_error(state, self.name, exc)
            raise

    def _matches_persona(self, title: str, persona: dict) -> bool:
        lower = title.lower()
        if any(pattern.lower() in lower for pattern in persona.get("titles", [])):
            return True
        seniority_levels = [s.lower() for s in (persona.get("seniority_levels") or [])]
        if seniority_levels:
            detected = self._seniority(title)
            if detected in (s.replace("-", " ") for s in seniority_levels) or detected in seniority_levels:
                return True
        return False

    def _seniority(self, title: str) -> str:
        lower = title.lower()
        if any(term in lower for term in ["chief", "ceo", "cto", "cro", "cfo", "coo", "cmo"]):
            return "c-suite"
        if "vp" in lower or "vice president" in lower:
            return "vp"
        if "director" in lower:
            return "director"
        if "manager" in lower or "lead" in lower:
            return "manager"
        return "individual contributor"

    def _department(self, title: str) -> str:
        lower = title.lower()
        if any(term in lower for term in ["sales", "revenue", "growth"]):
            return "sales"
        if any(term in lower for term in ["engineering", "technology", "platform", "product"]):
            return "engineering"
        if "marketing" in lower:
            return "marketing"
        return "general"
