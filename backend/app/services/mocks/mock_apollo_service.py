import hashlib
from typing import Any

from app.services.mocks.fixtures import find_catalog_company


class MockApolloService:
    """Mock Apollo service returning organization firmographics, people search, and contact data."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or "mock_apollo_key"

    async def enrich_organization(self, domain: str, company_name: str | None = None) -> dict[str, Any]:
        """Mock organization search/enrichment endpoint."""
        key = (domain or company_name or "company").lower().strip()
        hash_val = int(hashlib.md5(key.encode()).hexdigest(), 16)

        catalog_entry = find_catalog_company(key)
        if catalog_entry:
            name, c_domain, industry, headquarters, headcount, stage, funding = catalog_entry
            slug = c_domain.split(".")[0]
            display_name = name
            final_domain = domain or c_domain
            # Real-world Apollo headcount may slightly differ from Crunchbase (+/- 5%)
            headcount_val = max(10, headcount + ((hash_val % 11) - 5))
            parts = headquarters.split(", ")
            city = parts[0] if len(parts) > 0 else "San Francisco"
            state = parts[1] if len(parts) > 1 else "California"
            country = parts[2] if len(parts) > 2 else "United States"
            revenue = int(headcount_val * 140_000)
        else:
            headcounts = [35, 75, 160, 230, 420, 600, 950]
            revenue_multipliers = [0.5, 0.7, 1.0, 1.3]

            cities = [
                ("San Francisco", "California", "United States"),
                ("New York", "New York", "United States"),
                ("Austin", "Texas", "United States"),
                ("Boston", "Massachusetts", "United States"),
                ("Toronto", "Ontario", "Canada"),
            ]
            city, state, country = cities[hash_val % len(cities)]
            headcount_val = headcounts[hash_val % len(headcounts)]
            revenue = int(headcount_val * 125_000 * revenue_multipliers[hash_val % len(revenue_multipliers)])
            slug = key.split(".")[0].replace(" ", "-")
            display_name = (company_name or slug).replace("-", " ").title()
            final_domain = domain or f"{slug}.io"
            headquarters = f"{city}, {state}, {country}"
            industry = "B2B SaaS"

        return {
            "name": display_name,
            "domain": final_domain,
            "industry": industry,
            "headcount": headcount_val,
            "revenue_estimate_usd": revenue,
            "headquarters": headquarters,
            "city": city,
            "state": state,
            "country": country,
            "phone": f"+1 (555) {100 + (hash_val % 800):03d}-{2000 + (hash_val * 3 % 7000):04d}",
            "linkedin_url": f"https://www.linkedin.com/company/{slug}",
            "tech_stack": ["AWS", "PostgreSQL", "React", "Python"] if hash_val % 2 == 0 else ["GCP", "Kubernetes", "TypeScript"],
            "source": "apollo",
        }

    async def search_people(self, company: str, domain: str, titles: list[str]) -> list[dict[str, Any]]:
        """Mock Apollo mixed_people/search endpoint returning verified persona contacts."""
        key = f"{company}_{domain}".lower().strip()
        hash_val = int(hashlib.md5(key.encode()).hexdigest(), 16)

        first_names = ["Sarah", "Marcus", "Elena", "David", "Rachel", "Alex", "Samantha", "Jordan", "Chloe", "Vikram", "Jessica", "Liam"]
        last_names = ["Chen", "Vance", "Rostova", "Kim", "Adams", "Mercer", "Miller", "Lee", "Bennett", "Patel", "Foster", "Wright"]

        clean_titles = [t.strip() for t in titles if t.strip()] or ["VP Sales", "Chief Technology Officer", "Head of Product"]

        people = []
        for i, title in enumerate(clean_titles[:3]):
            fn = first_names[(hash_val + i * 2) % len(first_names)]
            ln = last_names[(hash_val + i * 4) % len(last_names)]
            name = f"{fn} {ln}"
            slug = f"{fn.lower()}-{ln.lower()}-{company.lower().replace(' ', '-')[:8]}"
            clean_domain = domain or f"{company.lower().replace(' ', '')}.com"
            email = f"{fn.lower()}.{ln.lower()}@{clean_domain}"
            phone = f"+1 (555) {300 + ((hash_val + i) % 600):03d}-{1000 + ((hash_val + i) * 5 % 8000):04d}"

            people.append({
                "name": name,
                "title": title,
                "company": company,
                "domain": clean_domain,
                "email": email,
                "email_confidence": 92,
                "phone": phone,
                "linkedin_url": f"https://www.linkedin.com/in/{slug}",
                "source": "apollo",
                "verified": True,
            })

        return people

    async def find_contact(self, name: str, company: str, linkedin_url: str | None = None) -> dict[str, Any]:
        """Mock Apollo contact match endpoint."""
        if not name:
            return {"phone": None, "linkedin_url": linkedin_url, "email": None, "employment_history": []}

        clean_name = name.strip()
        slug = clean_name.lower().replace(" ", "-")
        hash_code = sum(ord(c) for c in clean_name)
        phone = f"+1 (555) {200 + (hash_code % 700):03d}-{1000 + (hash_code * 7 % 9000):04d}"

        # Generate a realistic business email
        parts = clean_name.lower().split(" ")
        fn = parts[0] if parts else "contact"
        ln = parts[-1] if len(parts) > 1 else "user"
        company_slug = company.lower().replace(" ", "").replace(".", "") if company else "acme"
        email = f"{fn}.{ln}@{company_slug}.com"

        return {
            "phone": phone,
            "linkedin_url": linkedin_url or f"https://www.linkedin.com/in/{slug}",
            "email": email,
            "email_confidence": 88,
            "employment_history": [
                {
                    "title": "Executive",
                    "organization_name": company,
                    "current": True,
                    "start_date": "2021-06-01",
                }
            ],
            "source": "apollo",
        }
