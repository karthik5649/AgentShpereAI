import pytest
from unittest.mock import patch
from app.agents.company_discovery_agent import CompanyDiscoveryAgent
from app.agents.contact_enrichment_agent import ContactEnrichmentAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.common import get_llm
from app.services.icp_scoring_service import score_company
from app.services.mocks.mock_serper_service import MockSerperService
from app.core.config import Settings


@pytest.mark.asyncio
async def test_single_workflow_domains_strictly_unique(fake_redis):
    """1. Within a single workflow run, all company domains are strictly unique."""
    agent = CompanyDiscoveryAgent()
    state = {
        "workflow_id": "wf_test_unique",
        "user_id": "user_test",
        "icp": {
            "industry": ["B2B SaaS", "Fintech", "Cybersecurity"],
            "headcount_min": 10,
            "headcount_max": 5000,
            "funding_stages": ["Seed", "Series A", "Series B", "Growth"],
            "geography": ["United States", "North America"],
        },
        "raw_signals": [
            {"company": "Stripe", "domain": "stripe.com", "signal": "Stripe expands payments infrastructure", "trigger_type": "expansion"},
            {"company": "Stripe Inc", "domain": "stripe.com", "signal": "Stripe raises new round", "trigger_type": "funding_round"},
            {"company": "Datadog", "domain": "datadoghq.com", "signal": "Datadog expands hiring", "trigger_type": "headcount_growth"},
            {"company": "CrowdStrike", "domain": "crowdstrike.com", "signal": "CrowdStrike releases new product", "trigger_type": "product_launch"},
            {"company": "CrowdStrike Security", "domain": "crowdstrike.com", "signal": "CrowdStrike hiring spree", "trigger_type": "headcount_growth"},
        ],
    }

    res = await agent.run(state)
    discovered = res["discovered_companies"]
    assert len(discovered) >= 2, "Should discover at least 2 unique companies"
    domains = [c["domain"].strip().lower() for c in discovered if c.get("domain")]
    assert len(domains) == len(set(domains)), f"Duplicate domains found in discovered companies: {domains}"


def test_different_firmographics_produce_non_identical_scores():
    """2. Three companies with different firmographics against one ICP produce non-identical scores."""
    icp = {
        "industry": ["B2B SaaS"],
        "headcount_min": 50,
        "headcount_max": 250,
        "funding_stages": ["Series A", "Series B"],
        "geography": ["United States"],
        "revenue_min_usd": 2_000_000,
        "tech_stack": ["React", "Python"],
    }

    co_perfect = {
        "industry": "B2B SaaS",
        "headcount": 120,
        "funding_stage": "Series A",
        "headquarters": "San Francisco, CA, United States",
        "revenue_estimate_usd": 3_000_000,
        "tech_stack": ["React", "Python", "PostgreSQL"],
    }

    co_partial = {
        "industry": "B2B SaaS",
        "headcount": 25,  # below headcount min
        "funding_stage": "Seed",  # not Series A/B
        "headquarters": "Austin, TX, United States",
        "revenue_estimate_usd": 500_000,
        "tech_stack": ["Vue.js", "Python"],
    }

    co_poor = {
        "industry": "Healthcare",
        "headcount": 15000,
        "funding_stage": "Post-IPO",
        "headquarters": "Tokyo, Japan",
        "revenue_estimate_usd": 100_000_000,
        "tech_stack": ["Java", "Oracle"],
    }

    res_a = score_company(co_perfect, icp)
    res_b = score_company(co_partial, icp)
    res_c = score_company(co_poor, icp)

    scores = [res_a.score, res_b.score, res_c.score]
    # Verify scores are distinct
    assert len(set(scores)) == 3, f"Scores must all be distinct, got: {scores}"
    assert res_a.score > res_b.score > res_c.score, f"Scores not ordered by fit: {scores}"

    # Verify score breakdowns
    assert res_a.dimension_scores["industry"] > res_c.dimension_scores["industry"]
    assert res_a.dimension_scores["headcount"] > res_b.dimension_scores["headcount"]
    assert res_a.dimension_scores["funding_stage"] > res_b.dimension_scores["funding_stage"]


@pytest.mark.asyncio
async def test_triggers_across_workflow_not_all_identical():
    """3. Triggers across companies in a workflow are not all identical."""
    serper = MockSerperService()
    results = await serper.search("B2B SaaS enterprise software", search_type="news")
    triggers = [r.get("trigger_type") for r in results if r.get("trigger_type")]

    assert len(triggers) >= 3, "Expected at least 3 results with triggers"
    unique_triggers = set(triggers)
    assert len(unique_triggers) > 1, f"Expected varied triggers across results, got only: {unique_triggers}"
    # Verify not everything collapsed to headcount_growth
    assert not all(t == "headcount_growth" for t in triggers), "All triggers collapsed to headcount_growth"


@pytest.mark.asyncio
async def test_different_icps_yield_non_overlapping_company_sets():
    """4. Running with two different ICPs yields non-overlapping company sets."""
    serper = MockSerperService()
    res_fintech = await serper.search("Fintech payments banking", search_type="news")
    res_hr = await serper.search("Staffing HR Tech recruitment", search_type="news")

    domains_fintech = {r.get("domain", "").strip().lower() for r in res_fintech if r.get("domain")}
    domains_hr = {r.get("domain", "").strip().lower() for r in res_hr if r.get("domain")}

    assert len(domains_fintech) > 0 and len(domains_hr) > 0
    overlap = domains_fintech & domains_hr
    assert len(overlap) == 0, f"Expected non-overlapping company sets for Fintech vs HR Tech, got overlap: {overlap}"


@pytest.mark.asyncio
async def test_multi_provider_sourcing_and_contact_provenance(fake_db, fake_redis):
    """5. Multi-provider sourcing: verify contact provider provenance and merged company attributes."""
    # A. Company Discovery multi-provider merge
    agent = CompanyDiscoveryAgent()
    cb_details = {
        "name": "CloudSecure",
        "website_url": "https://cloudsecure.io",
        "industry": "Cybersecurity",
        "tech_stack": ["AWS", "Python"],
        "headcount": 150,
    }
    apollo_details = {
        "name": "CloudSecure Inc",
        "domain": "cloudsecure.io",
        "industry": "Cybersecurity",
        "tech_stack": ["Kubernetes", "Docker"],
        "headcount": 160,
    }
    merged = agent._merge_signal_and_details(
        signal={"company": "CloudSecure", "signal": "Raises $20M Series B", "trigger_type": "funding_round"},
        cb_details=cb_details,
        apollo_details=apollo_details,
        state={"workflow_id": "wf_test", "user_id": "u1"},
    )
    assert merged["domain"] == "cloudsecure.io"
    # Tech stack union
    assert "AWS" in merged["tech_stack"] and "Kubernetes" in merged["tech_stack"]
    # Evidence has corroborated entries
    sources = [e["source"] for e in merged["evidence"]]
    assert "crunchbase+apollo" in sources

    # B. Contact Enrichment provider provenance
    enrichment_agent = ContactEnrichmentAgent()
    state = {
        "workflow_id": "wf_enrich",
        "user_id": "user_test",
        "decision_makers": [
            {
                "workflow_id": "wf_enrich",
                "user_id": "user_test",
                "name": "Alex Smith",
                "company": "Datadog",
                "domain": "datadoghq.com",
                "title": "VP of Engineering",
                "linkedin_url": "https://linkedin.com/in/alexsmith",
            }
        ],
    }
    res = await enrichment_agent.run(state)
    contacts = res["enriched_contacts"]
    assert len(contacts) > 0
    c = contacts[0]
    assert c.get("email") is not None
    assert c.get("email_source") in ("hunter", "apollo"), f"Invalid email_source: {c.get('email_source')}"
    assert "phone_source" in c


@pytest.mark.asyncio
async def test_clean_fallback_when_ollama_offline(fake_redis):
    """6. Clean fallback when Ollama is offline."""
    offline_settings = Settings(
        LLM_PROVIDER="ollama",
        OLLAMA_BASE_URL="http://127.0.0.1:99999",
        OLLAMA_MODEL="qwen2.5:7b",
        MOCK_MODE=False,
    )

    with patch("app.agents.common.check_ollama_available", return_value=False):
        llm = get_llm(offline_settings)
        assert llm is None, "get_llm should return None when Ollama is offline"

    planner = PlannerAgent()
    state = {
        "session_id": "sess_fallback",
        "workflow_id": "wf_plan_fallback",
        "user_id": "user_test",
        "icp": {"industry": ["B2B SaaS"]},
        "personas": [{"role": "CTO"}],
        "triggers": ["funding_round"],
    }
    with patch("app.agents.planner_agent.get_settings", return_value=offline_settings):
        with patch("app.agents.common.check_ollama_available", return_value=False):
            plan_res = await planner.run(state)
            assert "execution_plan" in plan_res
            assert len(plan_res["execution_plan"]) > 0
            assert plan_res["execution_plan"]["agents"][0] == "search"
