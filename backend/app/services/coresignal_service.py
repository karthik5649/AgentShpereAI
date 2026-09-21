from __future__ import annotations

import logging
from typing import Any
import httpx

from app.core.config import get_settings
from app.core.exceptions import RateLimitError
from app.services.common import retry_async
from app.services.provider_tracker import provider_tracker

logger = logging.getLogger("agentsphere.services.coresignal")


def normalize_linkedin_url(url: str | None) -> str | None:
    """Ensure linkedin URLs are valid absolute URLs with https scheme."""
    if not url:
        return None
    clean = url.strip()
    if not clean:
        return None
    if clean.startswith("//"):
        return f"https:{clean}"
    if not clean.startswith(("http://", "https://")):
        # If it doesn't have domain part, add linkedin.com
        if clean.startswith("in/"):
            return f"https://www.linkedin.com/{clean}"
        return f"https://{clean}"
    return clean


class CoresignalService:
    BASE_URL = "https://api.coresignal.com/cdapi/v2"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or get_settings().CORESIGNAL_API_KEY

    async def agentic_search(
        self,
        prompt: str,
        entity: str = "employee",
        return_data: bool = True,
        threshold: float = 0.97,
    ) -> dict[str, Any]:
        """Execute raw Coresignal Fast Agentic Search."""
        if not self.api_key:
            logger.debug("Coresignal API key not configured, returning empty search response")
            return {"records": []}

        provider_tracker.record_request("coresignal")

        async def request() -> dict[str, Any]:
            url = f"{self.BASE_URL}/agentic_search/fast"
            payload = {
                "prompt": prompt,
                "return_data": return_data,
                "threshold": threshold,
                "entity": entity,
            }
            headers = {
                "apikey": self.api_key,
                "Content-Type": "application/json",
                "accept": "application/json",
            }
            async with httpx.AsyncClient(timeout=25.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code == 429:
                    raise RateLimitError("Coresignal API rate limit exceeded")
                if response.status_code == 403:
                    logger.warning("Coresignal API 403 Forbidden: check API key permissions")
                    return {"records": []}
                response.raise_for_status()
                data = response.json()
                provider_tracker.record_success("coresignal")
                return data

        try:
            return await retry_async(request)
        except Exception as exc:
            provider_tracker.record_failure("coresignal", str(exc))
            logger.warning("Coresignal agentic_search error: %s", exc)
            return {"records": []}

    async def search_employees(
        self,
        company: str,
        titles: list[str] | None = None,
        prompt: str | None = None,
        threshold: float = 0.97,
    ) -> list[dict[str, Any]]:
        """Search employees at a company matching titles or natural language prompt."""
        if not self.api_key:
            return []

        if not prompt:
            title_str = " or ".join(titles[:4]) if titles else "executive or leadership"
            prompt = f"Find current {title_str} at {company}"

        raw_response = await self.agentic_search(
            prompt=prompt,
            entity="employee",
            return_data=True,
            threshold=threshold,
        )

        records = self._extract_records(raw_response)
        results: list[dict[str, Any]] = []

        for item in records:
            if not isinstance(item, dict):
                continue
            name = (
                item.get("full_name")
                or item.get("name")
                or f"{item.get('first_name', '')} {item.get('last_name', '')}".strip()
            )
            if not name:
                continue

            title = (
                item.get("active_experience_title")
                or item.get("title")
                or item.get("job_title")
                or ""
            )

            raw_linkedin = (
                item.get("linkedin_url")
                or item.get("social_linkedin_url")
                or item.get("profile_url")
                or item.get("url")
            )
            linkedin_url = normalize_linkedin_url(raw_linkedin)

            department = (
                item.get("active_experience_department")
                or item.get("department")
                or "general"
            )

            results.append({
                "name": name,
                "title": title,
                "company": item.get("company_name") or company,
                "linkedin_url": linkedin_url,
                "department": department,
                "location": item.get("location_country") or item.get("location"),
                "source": "coresignal",
                "verified": bool(linkedin_url),
                "raw": item,
            })

        return results

    async def find_contact(
        self,
        name: str,
        company: str,
        linkedin_url: str | None = None,
    ) -> dict[str, Any]:
        """Find contact enrichment details for an individual via Coresignal."""
        if not self.api_key:
            return {
                "name": name,
                "company": company,
                "linkedin_url": normalize_linkedin_url(linkedin_url),
                "source": "coresignal",
            }

        prompt = f"Find employee {name} at {company}"
        raw_response = await self.agentic_search(
            prompt=prompt,
            entity="employee",
            return_data=True,
            threshold=0.95,
        )
        records = self._extract_records(raw_response)
        if not records:
            return {
                "name": name,
                "company": company,
                "linkedin_url": normalize_linkedin_url(linkedin_url),
                "source": "coresignal",
            }

        best = records[0]
        extracted_linkedin = (
            best.get("linkedin_url")
            or best.get("social_linkedin_url")
            or best.get("profile_url")
            or linkedin_url
        )

        history = best.get("experience") or best.get("employment_history") or []
        if not isinstance(history, list):
            history = []

        return {
            "name": best.get("full_name") or name,
            "title": best.get("active_experience_title") or best.get("title"),
            "company": best.get("company_name") or company,
            "department": best.get("active_experience_department"),
            "linkedin_url": normalize_linkedin_url(extracted_linkedin),
            "employment_history": history,
            "source": "coresignal",
        }

    def _extract_records(self, raw: dict[str, Any]) -> list[dict[str, Any]]:
        """Normalize various API response envelopes (array, records, results, data, or single object)."""
        if isinstance(raw, list):
            return [r for r in raw if isinstance(r, dict)]
        if not isinstance(raw, dict):
            return []

        for key in ("records", "results", "data", "employees"):
            val = raw.get(key)
            if isinstance(val, list):
                return [r for r in val if isinstance(r, dict)]

        # If raw itself is a single employee record
        if raw.get("id") or raw.get("full_name") or raw.get("active_experience_title"):
            return [raw]

        return []
