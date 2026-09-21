import pytest


def test_company_evidence_endpoint(client, fake_db):
    company_id = "co_test_evidence"
    fake_db.evidence.docs["ev_1"] = {
        "_id": "ev_1",
        "workflow_id": "wf_1",
        "entity_type": "company",
        "entity_id": company_id,
        "field": "industry",
        "value": "B2B SaaS",
        "source": "crunchbase",
        "confidence": 0.95,
        "evidence_type": "database",
        "retrieved_at": "2024-03-01T00:00:00Z",
    }
    fake_db.evidence.docs["ev_2"] = {
        "_id": "ev_2",
        "workflow_id": "wf_1",
        "entity_type": "company",
        "entity_id": company_id,
        "field": "domain_liveness",
        "value": True,
        "source": "http_check",
        "confidence": 1.0,
        "evidence_type": "api",
        "retrieved_at": "2024-03-01T00:01:00Z",
    }

    res = client.get(f"/api/v1/companies/{company_id}/evidence")
    assert res.status_code == 200
    data = res.json()
    assert data["company_id"] == company_id
    assert data["total"] == 2
    assert len(data["evidence"]) == 2
    assert data["evidence"][0]["field"] == "industry"
    assert data["evidence"][0]["evidence_type"] == "database"
    assert data["evidence"][1]["field"] == "domain_liveness"
    assert data["evidence"][1]["evidence_type"] == "api"


def test_conflict_detection_in_merge():
    from app.agents.company_discovery_agent import CompanyDiscoveryAgent

    agent = CompanyDiscoveryAgent()
    signal = {
        "company": "Acme Corp",
        "domain": "acme-news.com",
        "signal": "Acme Corp in cybersecurity raises $10M",
        "trigger_type": "funding_round",
        "source_url": "https://news.com/acme",
    }
    details = {
        "name": "Acme Corp",
        "website_url": "https://acmecorp.io",
        "industry": "B2B SaaS",
        "funding_stage": "Series A",
        "headquarters": "San Francisco, CA",
        "headcount": 100,
    }
    state = {
        "workflow_id": "wf_test",
        "user_id": "user_test",
        "icp": {"industry": ["Cybersecurity"], "geography": ["United States"]},
    }
    merged = agent._merge_signal_and_details(signal, details, state)
    assert "conflicts" in merged
    assert "evidence" in merged
    assert len(merged["evidence"]) > 0

    # Crunchbase industry (B2B SaaS) vs signal industry (Cybersecurity) conflict detected
    ind_conflicts = [c for c in merged["conflicts"] if c["field"] == "industry"]
    assert len(ind_conflicts) == 1
    sources = {s["source"]: s["value"] for s in ind_conflicts[0]["sources"]}
    assert sources["crunchbase"] == "B2B SaaS"
    assert sources["signal_inference"] == "Cybersecurity"
