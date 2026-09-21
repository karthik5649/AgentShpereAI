import pytest

import app.agents.validation_agent as validation_module
from app.agents.validation_agent import ValidationAgent


@pytest.mark.asyncio
async def test_validation_agent_saves_validated_company(monkeypatch):
    saved = {}

    async def fake_save_company(company):
        saved.update(company)
        return "co_1"

    async def fake_store_company_embedding(company):
        return "co_1"

    async def fake_domain_active(self, domain):
        return True

    monkeypatch.setattr(validation_module, "save_company", fake_save_company)
    monkeypatch.setattr(validation_module, "store_company_embedding", fake_store_company_embedding)
    monkeypatch.setattr(ValidationAgent, "_domain_active", fake_domain_active)

    state = {
        "workflow_id": "wf_1",
        "user_id": "user_test",
        "icp": {
            "industry": ["B2B SaaS"],
            "headcount_min": 10,
        },
        "discovered_companies": [
            {
                "name": "Acme",
                "domain": "acme.com",
                "industry": "B2B SaaS",
                "headcount": 50,
                "source_signal": {"trigger_type": "funding_round"},
                "linkedin_url": "x",
            }
        ],
    }
    result = await ValidationAgent().run(state)
    val_company = result["validated_companies"][0]
    assert val_company["validation_status"] == "validated"
    assert val_company["icp_status"] == "qualified"
    assert val_company["confidence_score"] > 0
    assert saved["name"] == "Acme"


@pytest.mark.asyncio
async def test_validation_agent_unqualified_handling(monkeypatch):
    async def fake_save_company(company):
        return "co_2"

    async def fake_store_company_embedding(company):
        return "co_2"

    async def fake_domain_inactive(self, domain):
        return False

    monkeypatch.setattr(validation_module, "save_company", fake_save_company)
    monkeypatch.setattr(validation_module, "store_company_embedding", fake_store_company_embedding)
    monkeypatch.setattr(ValidationAgent, "_domain_active", fake_domain_inactive)

    state = {
        "workflow_id": "wf_2",
        "user_id": "user_test",
        "icp": {"industry": ["B2B SaaS"]},
        "discovered_companies": [
            {"name": "DeadCo", "domain": "dead.invalid", "industry": "Hardware"}
        ],
    }
    result = await ValidationAgent().run(state)
    assert result["validated_companies"][0]["icp_status"] == "unqualified"
    assert result["validated_companies"][0]["validation_status"] == "unverified"
