from app.agents.company_discovery_agent import CompanyDiscoveryAgent


def test_company_discovery_icp_scoring_formula():
    agent = CompanyDiscoveryAgent()
    company = {
        "industry": "B2B SaaS",
        "headcount": 150,
        "funding_stage": "Series B",
        "headquarters": "United States",
        "revenue_estimate_usd": 10_000_000,
        "tech_stack": ["Salesforce"],
    }
    icp = {
        "industry": ["B2B SaaS"],
        "headcount_min": 50,
        "headcount_max": 500,
        "funding_stages": ["Series B"],
        "geography": ["United States"],
        "revenue_min_usd": 5_000_000,
        "tech_stack": ["Salesforce"],
    }
    score, matched = agent.score_company(company, icp)
    assert score == 1.0
    assert matched == ["industry", "headcount", "funding_stage", "geography", "revenue", "tech_stack"]


def test_company_discovery_unknown_criteria_handling():
    from app.services.icp_scoring_service import score_company

    company_missing_data = {
        "name": "SparseCo",
        "domain": "sparse.io",
        # Missing headcount, funding_stage, headquarters, revenue_estimate_usd, tech_stack
    }
    icp = {
        "industry": ["B2B SaaS"],
        "headcount_min": 50,
        "headcount_max": 500,
        "funding_stages": ["Series B"],
        "geography": ["United States"],
        "revenue_min_usd": 5_000_000,
        "tech_stack": ["Salesforce"],
    }
    score, matched, failed, unknown = score_company(company_missing_data, icp)
    assert score == 0.0
    assert len(matched) == 0
    assert "industry" in unknown
    assert "headcount" in unknown
    assert "funding_stage" in unknown
    assert "geography" in unknown
    assert "revenue" in unknown
    assert "tech_stack" in unknown


def test_company_discovery_custom_weights():
    from app.services.icp_scoring_service import score_company

    company = {
        "industry": "B2B SaaS",
        "headcount": 100,
    }
    icp = {
        "industry": ["B2B SaaS"],
        "headcount_min": 50,
        "headcount_max": 200,
        "scoring_weights": {
            "industry": 0.50,
            "headcount": 0.50,
        },
    }
    score, matched, failed, unknown = score_company(company, icp)
    assert score == 1.0
    assert "industry" in matched
    assert "headcount" in matched
