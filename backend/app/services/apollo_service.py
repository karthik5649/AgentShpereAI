import httpx
from typing import Any

from app.core.config import get_settings
from app.core.exceptions import RateLimitError
from app.services.common import retry_async
from app.services.provider_tracker import provider_tracker


class ApolloService:
    BASE_URL = "https://api.apollo.io/v1"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or get_settings().APOLLO_API_KEY

    async def enrich_organization(self, domain: str, company_name: str | None = None) -> dict[str, Any]:
        """Apollo organization enrichment endpoint (/v1/organizations/enrich)."""
        if not self.api_key:
            return {}

        provider_tracker.record_request("apollo")

        async def request() -> dict[str, Any]:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/organizations/enrich",
                    params={
                        "api_key": self.api_key,
                        "domain": domain,
                    },
                    headers={"Cache-Control": "no-cache", "Content-Type": "application/json"},
                )
                if response.status_code == 429:
                    raise RateLimitError("Apollo API rate limit exceeded")
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
                "linkedin_url": payload.get("linkedin_url"),
                "crunchbase_url": payload.get("crunchbase_url"),
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
                "api_key": self.api_key,
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
                    headers={"Cache-Control": "no-cache", "Content-Type": "application/json"},
                    json=payload_body,
                )
                if response.status_code == 429:
                    raise RateLimitError("Apollo API rate limit exceeded")
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
                    "linkedin_url": p.get("linkedin_url"),
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
        if not self.api_key:
            return {"phone": None, "linkedin_url": linkedin_url, "email": None, "employment_history": []}

        provider_tracker.record_request("apollo")

        async def request() -> dict[str, Any]:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/people/match",
                    headers={"Cache-Control": "no-cache", "Content-Type": "application/json"},
                    json={
                        "api_key": self.api_key,
                        "name": name,
                        "organization_name": company,
                        "linkedin_url": linkedin_url,
                    },
                )
                if response.status_code == 429:
                    raise RateLimitError("Apollo API rate limit exceeded")
                response.raise_for_status()
                payload = response.json().get("person") or {}

            provider_tracker.record_success("apollo")
            phones = payload.get("phone_numbers") or []
            first_phone = phones[0].get("raw_number") if phones and isinstance(phones[0], dict) else payload.get("phone")
            return {
                "phone": first_phone,
                "linkedin_url": payload.get("linkedin_url") or linkedin_url,
                "email": payload.get("email"),
                "employment_history": payload.get("employment_history") or [],
                "source": "apollo",
            }

        try:
            return await retry_async(request)
        except Exception as exc:
            provider_tracker.record_failure("apollo", str(exc))
            return {"phone": None, "linkedin_url": linkedin_url, "email": None, "employment_history": []}
