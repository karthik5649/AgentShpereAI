import pytest

from app.core.config import get_settings
from app.memory.vector_store import init_vector_store
from app.registry.agent_registry import FUNCTIONAL_AGENT_REGISTRY


def test_agent_registry_schemas():
    for agent_id, agent_cls in FUNCTIONAL_AGENT_REGISTRY.items():
        assert hasattr(agent_cls, "input_schema")
        assert hasattr(agent_cls, "output_schema")
        assert agent_cls.input_schema is not None
        assert agent_cls.output_schema is not None


def test_test_company_discovery_agent_endpoint(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "MOCK_MODE", True)
    init_vector_store(None, ":memory:")

    payload = {
        "icp": {
            "industry": ["B2B SaaS"],
            "headcount_min": 50,
            "headcount_max": 500,
            "funding_stages": ["Series B"],
            "geography": ["United States"],
        },
        "raw_signals": [
            {
                "company": "CloudScale Systems",
                "domain": "cloudscale.io",
                "signal": "CloudScale Systems raises $25M Series B funding round",
                "trigger_type": "funding_round",
                "source_url": "https://news.com/cloudscale",
            }
        ],
    }

    res = client.post("/api/v1/agents/company_discovery_agent/test", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["agent_id"] == "company_discovery_agent"
    assert data["status"] == "success"
    assert "discovered_companies" in data["output"]
    companies = data["output"]["discovered_companies"]
    assert len(companies) > 0
    assert companies[0]["name"] == "CloudScale Systems"
    assert companies[0]["icp_match_score"] > 0


def test_test_validation_agent_endpoint(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "MOCK_MODE", True)
    init_vector_store(None, ":memory:")

    from app.agents.validation_agent import ValidationAgent

    async def fake_domain_active(self, domain):
        return True

    monkeypatch.setattr(ValidationAgent, "_domain_active", fake_domain_active)

    payload = {
        "icp": {
            "industry": ["B2B SaaS"],
            "headcount_min": 10,
        },
        "discovered_companies": [
            {
                "name": "Acme Cloud",
                "domain": "acmecloud.io",
                "industry": "B2B SaaS",
                "headcount": 100,
                "funding_stage": "Series A",
                "headquarters": "San Francisco, CA, United States",
            }
        ],
    }

    res = client.post("/api/v1/agents/validation_agent/test", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["agent_id"] == "validation_agent"
    assert data["status"] == "success"
    assert "validated_companies" in data["output"]
    companies = data["output"]["validated_companies"]
    assert len(companies) == 1
    assert companies[0]["icp_status"] == "qualified"
    assert companies[0]["validation_status"] == "validated"


def test_unknown_agent_test_404(client):
    res = client.post("/api/v1/agents/unknown_agent_xyz/test", json={})
    assert res.status_code == 404
