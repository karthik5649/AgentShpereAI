from __future__ import annotations

import logging
from typing import Any
import httpx

from app.core.config import get_settings
from app.core.exceptions import RateLimitError
from app.services.common import retry_async
from app.services.coresignal_service import normalize_linkedin_url
from app.services.provider_tracker import provider_tracker

logger = logging.getLogger("agentsphere.services.apollo")


class ApolloService:
    BASE_URL = "https://api.apollo.io/v1"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or get_settings().APOLLO_API_KEY

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "Cache-Control": "no-cache",
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        return headers

    async def enrich_organization(self, domain: str, company_name: str | None = None) -> dict[str, Any]:
        """Apollo organization enrichment endpoint (/v1/organizations/enrich)."""
        if not self.api_key:
            return {}

        provider_tracker.record_request("apollo")

        async def request() -> dict[str, Any]:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/organizations/enrich",
                    params={"domain": domain},
                    headers=self._get_headers(),
                )
                if response.status_code == 429:
                    raise RateLimitError("Apollo API rate limit exceeded")
                if response.status_code in (403, 401):
                    logger.warning("Apollo enrich_organization access denied or unauthorized: %s", response.status_code)
                    return {}
                response.raise_for_status()
                payload = response.json().get("organization") or {}

            provider_tracker.record_success("apollo")
            raw_city = payload.get("city")
            raw_state = payload.get("state")
            raw_country = payload.get("country")
            hq_parts = [p for p in [raw_city, raw_state, raw_country] if p]

            return {
                "name": payload.get("name") or company_name,
                "domain": payload.get("primary_domain") or domain,
                "industry": payload.get("industry"),
                "headcount": payload.get("estimated_num_employees"),
                "revenue_estimate_usd": payload.get("annual_revenue"),
                "headquarters": ", ".join(hq_parts) if hq_parts else None,
                "city": raw_city,
                "state": raw_state,
                "country": raw_country,
                "phone": payload.get("phone"),
                "linkedin_url": normalize_linkedin_url(payload.get("linkedin_url")),
                "tech_stack": [t.get("name") for t in (payload.get("current_technologies") or []) if t.get("name")],
                "source": "apollo",
            }

        try:
            return await retry_async(request)
        except Exception as exc:
            provider_tracker.record_failure("apollo", str(exc))
            return {}

    async def search_people(self, company: str, domain: str, titles: list[str]) -> list[dict[str, Any]]:
        """Apollo people search endpoint (/v1/mixed_people/search)."""
        if not self.api_key:
            return []

        provider_tracker.record_request("apollo")

        async def request() -> list[dict[str, Any]]:
            payload_body: dict[str, Any] = {
                "page": 1,
                "per_page": 5,
            }
            if domain:
                payload_body["q_organization_domains"] = domain
            if company:
                payload_body["q_organization_name"] = company
            if titles:
                payload_body["person_titles"] = titles[:5]

            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/mixed_people/search",
                    headers=self._get_headers(),
                    json=payload_body,
                )
                if response.status_code == 429:
                    raise RateLimitError("Apollo API rate limit exceeded")
                if response.status_code in (403, 401):
                    logger.warning("Apollo mixed_people/search access denied (requires paid Apollo plan): %s", response.status_code)
                    return []
                response.raise_for_status()
                data = response.json().get("people") or []

            provider_tracker.record_success("apollo")
            results = []
            for p in data:
                phones = p.get("phone_numbers") or []
                phone = phones[0].get("raw_number") if phones and isinstance(phones[0], dict) else p.get("phone")
                results.append({
                    "name": p.get("name"),
                    "title": p.get("title"),
                    "company": company,
                    "domain": domain,
                    "email": p.get("email"),
                    "phone": phone,
                    "linkedin_url": normalize_linkedin_url(p.get("linkedin_url")),
                    "source": "apollo",
                    "verified": bool(p.get("email")),
                })
            return results

        try:
            return await retry_async(request)
        except Exception as exc:
            provider_tracker.record_failure("apollo", str(exc))
            return []

    async def find_contact(self, name: str, company: str, linkedin_url: str | None = None) -> dict[str, Any]:
        """Apollo people match endpoint (/v1/people/match)."""
        clean_linkedin = normalize_linkedin_url(linkedin_url)
        if not self.api_key:
            return {"phone": None, "linkedin_url": clean_linkedin, "email": None, "employment_history": []}

        provider_tracker.record_request("apollo")

        async def request() -> dict[str, Any]:
            match_body: dict[str, Any] = {
                "name": name,
                "organization_name": company,
            }
            if clean_linkedin:
                match_body["linkedin_url"] = clean_linkedin

            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/people/match",
                    headers=self._get_headers(),
                    json=match_body,
                )
                if response.status_code == 429:
                    raise RateLimitError("Apollo API rate limit exceeded")
                if response.status_code in (403, 401):
                    logger.warning("Apollo people/match endpoint access denied (requires paid plan): %s", response.status_code)
                    return {"phone": None, "linkedin_url": clean_linkedin, "email": None, "employment_history": []}
                response.raise_for_status()
                payload = response.json().get("person") or {}

            provider_tracker.record_success("apollo")
            phones = payload.get("phone_numbers") or []
            first_phone = phones[0].get("raw_number") if phones and isinstance(phones[0], dict) else payload.get("phone")
            return {
                "phone": first_phone,
                "linkedin_url": normalize_linkedin_url(payload.get("linkedin_url")) or clean_linkedin,
                "email": payload.get("email"),
                "employment_history": payload.get("employment_history") or [],
                "source": "apollo",
            }

        try:
            return await retry_async(request)
        except Exception as exc:
            provider_tracker.record_failure("apollo", str(exc))
            return {"phone": None, "linkedin_url": clean_linkedin, "email": None, "employment_history": []}
