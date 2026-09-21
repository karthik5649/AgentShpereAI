import pytest
from app.core.config import get_settings
from app.domain.domain_profile import DEFAULT_DOMAIN_PROFILES
from app.memory.document_store import save_domain_profile, get_workflow


@pytest.mark.asyncio
async def test_seed_domain_profiles_and_list(client):
    # Ensure default profiles are saved
    for profile in DEFAULT_DOMAIN_PROFILES:
        await save_domain_profile(profile.model_dump())

    res = client.get("/api/v1/domain-profiles")
    assert res.status_code == 200
    profiles = res.json()
    assert len(profiles) >= 2
    ids = [p["id"] for p in profiles]
    assert "b2b_saas" in ids
    assert "staffing_recruiting" in ids


def test_get_domain_profile_by_id(client):
    res = client.get("/api/v1/domain-profiles/b2b_saas")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "b2b_saas"
    assert data["name"] == "B2B SaaS"
    assert "industry" in data["default_weights"]
    assert data["default_cutoff"] == 0.65


def test_get_unknown_domain_profile_404(client):
    res = client.get("/api/v1/domain-profiles/non_existent_profile_xyz")
    assert res.status_code == 404


def test_create_custom_domain_profile(client):
    payload = {
        "id": "healthtech",
        "name": "HealthTech AI",
        "description": "Medical & Clinical AI ventures",
        "icp_dimensions": ["industry", "compliance_certifications", "geography"],
        "default_weights": {
            "industry": 0.40,
            "compliance_certifications": 0.40,
            "geography": 0.20,
        },
        "default_cutoff": 0.75,
        "default_triggers": ["fda_approval", "clinical_trial_phase2"],
        "persona_vocabulary": [
            {"title": "Chief Medical Officer", "department": "Clinical", "seniority": "C-Level"}
        ],
    }
    res = client.post("/api/v1/domain-profiles", json=payload)
    assert res.status_code == 201
    created = res.json()
    assert created["id"] == "healthtech"
    assert created["default_cutoff"] == 0.75

    get_res = client.get("/api/v1/domain-profiles/healthtech")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "HealthTech AI"


@pytest.mark.asyncio
async def test_workflow_inherits_domain_profile_defaults(client, monkeypatch):
    from app.domain.domain_profile import DEFAULT_DOMAIN_PROFILES
    for profile in DEFAULT_DOMAIN_PROFILES:
        await save_domain_profile(profile.model_dump())

    # Create workflow referencing "b2b_saas" without custom weights/cutoff/triggers
    payload = {
        "name": "B2B Outreach Campaign",
        "domain_profile_id": "b2b_saas",
        "icp": {
            "industry": ["B2B SaaS"],
            "headcount_min": 10,
            "headcount_max": 200,
            "funding_stages": ["Series A"],
            "geography": ["United States"],
        },
        "personas": [
            {
                "name": "CTO",
                "titles": ["Chief Technology Officer"],
                "seniority_levels": ["C-Level"],
                "priority": 1,
            }
        ],
        "triggers": [],  # empty triggers to verify inheritance
    }

    res = client.post("/api/v1/workflows", json=payload)
    assert res.status_code == 201
    wf_id = res.json()["workflow_id"]

    saved_wf = await get_workflow(wf_id)
    assert saved_wf is not None
    assert saved_wf.get("domain_profile_id") == "b2b_saas"
    assert saved_wf["icp"]["weights"]["industry"] == 0.25
    assert saved_wf["icp"]["cutoff"] == 0.65
    assert "funding_round" in saved_wf["triggers"]
