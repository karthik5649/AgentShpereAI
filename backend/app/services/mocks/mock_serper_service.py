import hashlib
import re
from typing import Any

from app.services.mocks.fixtures import COMPANY_CATALOG

# Derive candidate tuples (name, domain, industry) from shared catalog
MOCK_COMPANY_POOL = [(c[0], c[1], c[2]) for c in COMPANY_CATALOG]


class MockSerperService:
    """Mock Serper service producing realistic, query-driven news and LinkedIn search results."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or "mock_serper_key"

    async def search(self, query: str, search_type: str = "news") -> list[dict[str, Any]]:
        query_lower = query.lower()

        # Handle LinkedIn dork searches: site:linkedin.com/in "<company>" (<titles>)
        if "site:linkedin.com/in" in query_lower:
            return self._mock_linkedin_results(query)

        # General news / trigger search
        return self._mock_news_results(query, search_type)

    def _mock_linkedin_results(self, query: str) -> list[dict[str, Any]]:
        match = re.search(r'"([^"]+)"', query)
        company = match.group(1) if match else "Acme"
        c_hash = int(hashlib.md5(company.encode()).hexdigest(), 16)

        first_names = ["Sarah", "Marcus", "Elena", "David", "Rachel", "Alex", "Samantha", "Jordan", "Chloe", "Vikram", "Jessica", "Liam"]
        last_names = ["Chen", "Vance", "Rostova", "Kim", "Adams", "Mercer", "Miller", "Lee", "Bennett", "Patel", "Foster", "Wright"]

        # Parse desired title patterns from query
        is_tech = any(term in query.lower() for term in ["cto", "engineering", "technical", "architect", "developer"])
        is_hr = any(term in query.lower() for term in ["hr", "recruiter", "talent", "staffing", "people"])
        is_sales = any(term in query.lower() for term in ["sales", "cro", "revenue", "business development", "account"])

        if is_tech:
            title_templates = ["Chief Technology Officer", "VP of Engineering", "Head of Platform Architecture", "Director of Software Engineering"]
            snippets = [
                "Leading core platform architecture and distributed AI infrastructure",
                "Managing 40+ senior software engineers, microservices and devops pipelines",
                "Spearheading technical roadmap and scalable cloud operations",
            ]
        elif is_hr:
            title_templates = ["Head of Talent Acquisition", "VP of People & Culture", "Director of Human Resources", "Chief People Officer"]
            snippets = [
                "Leading global recruiting initiatives and strategic headcount growth",
                "Scaling technical and enterprise sales teams across international hubs",
                "Overseeing organizational culture, hiring pipelines and executive onboarding",
            ]
        elif is_sales:
            title_templates = ["VP of Enterprise Sales", "Chief Revenue Officer", "Head of Business Development", "Director of Sales"]
            snippets = [
                "Driving enterprise ARR expansion and strategic mid-market customer acquisition",
                "Leading high-performance sales teams and global go-to-market execution",
                "Scaling outbound revenue operations and Fortune 500 partnerships",
            ]
        else:
            title_templates = ["VP of Operations", "Chief Operating Officer", "Head of Product", "Director of Strategy"]
            snippets = [
                "Driving operational excellence and strategic product expansion",
                "Overseeing cross-functional growth and enterprise product delivery",
            ]

        results = []
        for i in range(3):
            fn = first_names[(c_hash + i * 3) % len(first_names)]
            ln = last_names[(c_hash + i * 5) % len(last_names)]
            name = f"{fn} {ln}"
            title = title_templates[(c_hash + i) % len(title_templates)]
            snippet = snippets[(c_hash + i) % len(snippets)]
            slug = f"{fn.lower()}-{ln.lower()}-{company.lower().replace(' ', '-')[:8]}"

            results.append({
                "title": f"{name} - {title} at {company} | LinkedIn",
                "snippet": f"{snippet} at {company}. Seasoned executive driving high-velocity scale.",
                "link": f"https://www.linkedin.com/in/{slug}",
                "source": "linkedin.com",
                "date": "2024-03-01",
            })

        return results

    def _mock_news_results(self, query: str, search_type: str) -> list[dict[str, Any]]:
        query_lower = query.lower()
        seed_str = f"{query}_{search_type}"
        hash_val = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)

        # Filter candidate pool based on industry keywords in the query
        if "staffing" in query_lower or "recruiting" in query_lower:
            candidates = [c for c in MOCK_COMPANY_POOL if c[2] == "Staffing"]
        elif "fintech" in query_lower or "finance" in query_lower:
            candidates = [c for c in MOCK_COMPANY_POOL if c[2] == "Fintech"]
        elif "health" in query_lower or "med" in query_lower:
            candidates = [c for c in MOCK_COMPANY_POOL if c[2] in ("Healthcare", "Digital Health", "HealthTech")]
        elif "security" in query_lower or "cyber" in query_lower:
            candidates = [c for c in MOCK_COMPANY_POOL if c[2] in ("CyberSecurity", "Cloud Infrastructure")]
        elif "cloud" in query_lower or "infra" in query_lower:
            candidates = [c for c in MOCK_COMPANY_POOL if c[2] == "Cloud Infrastructure"]
        else:
            candidates = [c for c in MOCK_COMPANY_POOL if c[2] in ("B2B SaaS", "Cloud Infrastructure", "CyberSecurity")]

        if not candidates:
            candidates = MOCK_COMPANY_POOL

        # Detect which triggers were specifically asked about
        detected_triggers = []
        if any(t in query_lower for t in ["funding", "series a", "series b", "raises", "capital"]):
            detected_triggers.append("funding_round")
        if any(t in query_lower for t in ["hiring", "headcount", "recruiting", "talent"]):
            detected_triggers.append("headcount_growth")
        if any(t in query_lower for t in ["appoint", "executive", "cro", "cto", "ceo", "leadership"]):
            detected_triggers.append("new_executive")
        if any(t in query_lower for t in ["product", "launch", "release", "platform"]):
            detected_triggers.append("product_launch")
        if any(t in query_lower for t in ["expand", "expansion", "office", "market"]):
            detected_triggers.append("expansion")

        all_triggers = ["funding_round", "headcount_growth", "new_executive", "product_launch", "expansion"]
        # Prioritize detected triggers, then append remaining triggers to ensure natural variation
        possible_triggers = detected_triggers + [t for t in all_triggers if t not in detected_triggers]

        # Select 3-4 distinct companies offset so 'news' and 'search' return disjoint firms
        count = 3 if search_type == "search" else 4
        half_pool = max(count, len(candidates) // 2)
        offset = 0 if search_type == "news" else half_pool
        start_idx = (hash_val + offset) % len(candidates)
        selected_companies = [
            candidates[(start_idx + i) % len(candidates)]
            for i in range(count)
        ]

        results = []
        amounts = ["$12M", "$18M", "$25M", "$35M", "$42M", "$60M"]
        rounds = ["Series A", "Series B", "Series B", "Series C", "Growth"]

        for idx, (company, domain, industry) in enumerate(selected_companies):
            # Guarantee every company card in the batch receives a distinct trigger
            trigger = possible_triggers[idx % len(possible_triggers)]
            amount = amounts[(hash_val + idx) % len(amounts)]
            rnd = rounds[(hash_val + idx) % len(rounds)]

            if trigger == "headcount_growth":
                title = f"{company} announces major hiring surge to double engineering and sales headcount"
                snippet = f"{company}, a high-growth {industry} provider, is expanding its team by 120 employees following surging enterprise demand."
            elif trigger == "new_executive":
                title = f"{company} appoints seasoned enterprise executive as Chief Revenue Officer"
                snippet = f"{company} brings on new leadership to drive enterprise expansion and international sales growth."
            elif trigger == "product_launch":
                title = f"{company} launches next-generation enterprise intelligence platform"
                snippet = f"{company} announces the general availability of its new automated AI workflow product suite."
            elif trigger == "expansion":
                title = f"{company} announces European expansion and opens new London headquarters"
                snippet = f"Rapidly scaling {industry} leader {company} opens its European headquarters to serve EMEA enterprise clients."
            else:
                title = f"{company} raises {amount} {rnd} funding round led by top Silicon Valley VCs"
                snippet = f"{company} ({domain}) secures {amount} in {rnd} financing to accelerate product development and global expansion."

            results.append({
                "title": title,
                "snippet": snippet,
                "link": f"https://techcrunch.com/news/{company.lower().replace(' ', '-')}-{amount.lower()}",
                "date": "2024-05-15",
                "source": "techcrunch.com",
                "company": company,
                "domain": domain,
                "trigger_type": trigger,
            })

        return results
