from __future__ import annotations

import hashlib
from typing import Any

from app.services.coresignal_service import normalize_linkedin_url


class MockCoresignalService:
    """Mock Coresignal service returning agentic search employee profiles."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or "mock_coresignal_key"

    async def agentic_search(
        self,
        prompt: str,
        entity: str = "employee",
        return_data: bool = True,
        threshold: float = 0.97,
    ) -> dict[str, Any]:
        """Mock raw Coresignal Fast Agentic Search."""
        return {
            "records found": 3,
            "threshold": threshold,
            "entity": entity,
            "records": [
                {
                    "id": 10101,
                    "full_name": "Sarah Chen",
                    "active_experience_title": "VP of Engineering",
                    "active_experience_department": "Engineering",
                    "company_name": "Target Corp",
                    "location_country": "United States",
                    "linkedin_url": "https://www.linkedin.com/in/sarah-chen-eng",
                },
                {
                    "id": 10102,
                    "full_name": "Marcus Vance",
                    "active_experience_title": "Chief Technology Officer",
                    "active_experience_department": "Engineering",
                    "company_name": "Target Corp",
                    "location_country": "United States",
                    "linkedin_url": "https://www.linkedin.com/in/marcus-vance-cto",
                },
            ],
        }

    async def search_employees(
        self,
        company: str,
        titles: list[str] | None = None,
        prompt: str | None = None,
        threshold: float = 0.97,
    ) -> list[dict[str, Any]]:
        """Mock employee search by company and titles."""
        key = f"{company}_{''.join(titles or [])}".lower().strip()
        hash_val = int(hashlib.md5(key.encode()).hexdigest(), 16)

        first_names = ["Sarah", "Marcus", "Elena", "David", "Rachel", "Alex", "Samantha", "Jordan", "Chloe", "Vikram", "Jessica", "Liam"]
        last_names = ["Chen", "Vance", "Rostova", "Kim", "Adams", "Mercer", "Miller", "Lee", "Bennett", "Patel", "Foster", "Wright"]

        clean_titles = [t.strip() for t in (titles or []) if t.strip()] or [
            "Chief Technology Officer",
            "VP of Engineering",
            "Head of Product",
        ]

        results = []
        for i, title in enumerate(clean_titles[:3]):
            fn = first_names[(hash_val + i * 3) % len(first_names)]
            ln = last_names[(hash_val + i * 5) % len(last_names)]
            name = f"{fn} {ln}"
            comp_slug = company.lower().replace(" ", "-")[:10]
            slug = f"{fn.lower()}-{ln.lower()}-{comp_slug}"

            dept = "Engineering"
            if any(term in title.lower() for term in ["sales", "revenue", "growth"]):
                dept = "Sales"
            elif any(term in title.lower() for term in ["marketing"]):
                dept = "Marketing"
            elif any(term in title.lower() for term in ["product"]):
                dept = "Product"

            results.append({
                "name": name,
                "title": title,
                "company": company,
                "linkedin_url": f"https://www.linkedin.com/in/{slug}",
                "department": dept,
                "location": "United States",
                "source": "coresignal",
                "verified": True,
                "raw": {
                    "id": 20000 + (hash_val + i) % 50000,
                    "full_name": name,
                    "active_experience_title": title,
                    "company_name": company,
                    "linkedin_url": f"https://www.linkedin.com/in/{slug}",
                },
            })

        return results

    async def find_contact(
        self,
        name: str,
        company: str,
        linkedin_url: str | None = None,
    ) -> dict[str, Any]:
        """Mock contact enrichment lookup."""
        clean_name = name.strip()
        slug = clean_name.lower().replace(" ", "-")
        final_linkedin = normalize_linkedin_url(linkedin_url) or f"https://www.linkedin.com/in/{slug}"

        return {
            "name": clean_name,
            "title": "Vice President",
            "company": company,
            "department": "Executive",
            "linkedin_url": final_linkedin,
            "employment_history": [
                {
                    "title": "Vice President",
                    "organization_name": company,
                    "current": True,
                    "start_date": "2022-01-01",
                }
            ],
            "source": "coresignal",
        }
