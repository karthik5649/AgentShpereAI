import hashlib
from datetime import UTC, datetime
from typing import Any

from app.services.mocks.fixtures import find_catalog_company


class MockCrunchbaseService:
    """Mock Crunchbase service returning rich, deterministic, and widely varied company firmographics."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or "mock_crunchbase_key"

    async def get_company(self, company_name_or_domain: str) -> dict[str, Any]:
        if not company_name_or_domain:
            return {}

        clean_name = company_name_or_domain.strip().lower()
        hash_val = int(hashlib.md5(clean_name.encode()).hexdigest(), 16)

        # 1. Check shared catalog first for canonical firmographics
        catalog_entry = find_catalog_company(clean_name)
        if catalog_entry:
            name, domain, industry, headquarters, headcount, stage, funding = catalog_entry
            slug = domain.split(".")[0]
            display_name = name
            revenue_multipliers = [0.8, 1.1, 1.3, 0.9, 1.5]
            revenue = int(funding * revenue_multipliers[hash_val % len(revenue_multipliers)])
        else:
            # 2. Derive deterministic firmographics for arbitrary companies
            headcount_options = [25, 45, 80, 140, 210, 340, 520, 850, 1200]
            funding_stages = ["Seed", "Series A", "Series B", "Series C", "Series D", "Growth"]
            funding_amounts = [3_000_000, 12_000_000, 25_000_000, 45_000_000, 80_000_000, 120_000_000]
            revenue_multipliers = [0.4, 0.65, 0.9, 1.2, 1.5]

            locations = [
                "San Francisco, California, United States",
                "New York, New York, United States",
                "Austin, Texas, United States",
                "Boston, Massachusetts, United States",
                "Seattle, Washington, United States",
                "Denver, Colorado, United States",
                "Chicago, Illinois, United States",
                "Atlanta, Georgia, United States",
                "Toronto, Ontario, Canada",
                "London, United Kingdom",
            ]

            headcount = headcount_options[hash_val % len(headcount_options)]
            stage_idx = hash_val % len(funding_stages)
            stage = funding_stages[stage_idx]
            funding = funding_amounts[stage_idx]
            revenue = int(funding * revenue_multipliers[hash_val % len(revenue_multipliers)])
            headquarters = locations[hash_val % len(locations)]

            # Infer industry with strict substring matching
            if any(term in clean_name for term in ["health", "bio", "care", "med", "clinical"]):
                industry = "HealthTech"
            elif any(term in clean_name for term in ["pay", "ledger", "moneta", "invoice", "fintech", "settle", "treasury"]):
                industry = "Fintech"
            elif any(term in clean_name for term in ["staff", "talent", "workforce", "hiring", "people", "recruit"]):
                industry = "Staffing"
            elif any(term in clean_name for term in ["guard", "sentry", "zero", "cipher", "security", "defense"]):
                industry = "CyberSecurity"
            elif any(term in clean_name for term in ["kube", "infra", "mesh", "packet", "cloud", "vortex"]):
                industry = "Cloud Infrastructure"
            elif any(term in clean_name for term in ["cart", "retail", "shop", "store", "commerce", "logistics", "ship"]):
                industry = "E-Commerce"
            else:
                industry = "B2B SaaS"

            slug = clean_name.replace(" ", "-").replace(".io", "").replace(".com", "").replace(".tech", "").replace(".dev", "")
            domain = f"{slug}.io" if not clean_name.endswith((".com", ".io", ".ai", ".co", ".tech", ".dev")) else clean_name
            display_name = company_name_or_domain.split(".")[0].replace("-", " ").title()

        tech_stacks = [
            ["Python", "FastAPI", "React", "PostgreSQL", "AWS"],
            ["Go", "Kubernetes", "PostgreSQL", "React", "GCP"],
            ["TypeScript", "Node.js", "Next.js", "MongoDB", "AWS"],
            ["Python", "PyTorch", "FastAPI", "Redis", "AWS", "Snowflake"],
            ["Java", "Spring Boot", "Angular", "Oracle", "Azure"],
            ["Rust", "Kafka", "PostgreSQL", "Docker", "AWS"],
            ["Python", "FastAPI", "React", "PostgreSQL", "GCP", "Kubernetes"],
            ["TypeScript", "Next.js", "Tailwind", "Supabase", "AWS"],
        ]
        tech_stack = tech_stacks[hash_val % len(tech_stacks)]

        return {
            "name": display_name,
            "domain": domain,
            "description": f"{display_name} is an enterprise {industry} platform delivering high-velocity operations.",
            "website_url": f"https://{domain}",
            "industry": industry,
            "headcount": headcount,
            "funding_stage": stage,
            "funding_amount_usd": funding,
            "revenue_estimate_usd": revenue,
            "headquarters": headquarters,
            "linkedin_url": f"https://www.linkedin.com/company/{slug}",
            "crunchbase_url": f"https://www.crunchbase.com/organization/{slug}",
            "tech_stack": tech_stack,
            "source": "crunchbase",
            "updated_at": datetime.now(UTC).isoformat(),
        }
