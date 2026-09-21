import pytest
from unittest.mock import AsyncMock, patch
import httpx

from app.services.coresignal_service import CoresignalService, normalize_linkedin_url
from app.services.mocks.mock_coresignal_service import MockCoresignalService
from app.agents.contact_enrichment_agent import ContactEnrichmentAgent
from app.agents.decision_maker_agent import DecisionMakerAgent


def test_normalize_linkedin_url():
    assert normalize_linkedin_url(None) is None
    assert normalize_linkedin_url("") is None
    assert normalize_linkedin_url("   ") is None
    assert normalize_linkedin_url("https://www.linkedin.com/in/satyanadella") == "https://www.linkedin.com/in/satyanadella"
    assert normalize_linkedin_url("http://linkedin.com/in/satyanadella") == "http://linkedin.com/in/satyanadella"
    assert normalize_linkedin_url("linkedin.com/in/satyanadella") == "https://linkedin.com/in/satyanadella"
    assert normalize_linkedin_url("www.linkedin.com/in/satyanadella") == "https://www.linkedin.com/in/satyanadella"
    assert normalize_linkedin_url("//www.linkedin.com/in/satyanadella") == "https://www.linkedin.com/in/satyanadella"
    assert normalize_linkedin_url("in/satyanadella") == "https://www.linkedin.com/in/satyanadella"


@pytest.mark.asyncio
async def test_mock_coresignal_service():
    service = MockCoresignalService()
    search_res = await service.search_employees("Target Corp", ["VP of Engineering"])
    assert len(search_res) > 0
    assert search_res[0]["name"]
    assert search_res[0]["title"]
    assert search_res[0]["linkedin_url"].startswith("https://")
    assert search_res[0]["source"] == "coresignal"

    contact = await service.find_contact("Sarah Chen", "Target Corp")
    assert contact["name"] == "Sarah Chen"
    assert contact["linkedin_url"].startswith("https://")


@pytest.mark.asyncio
async def test_coresignal_service_request_building():
    service = CoresignalService(api_key="test_cs_key")

    mock_resp = {
        "records": [
            {
                "id": 999,
                "full_name": "Alice Wonderland",
                "active_experience_title": "Chief Technology Officer",
                "active_experience_department": "Engineering",
                "company_name": "Wonderland Inc",
                "linkedin_url": "linkedin.com/in/alicewonderland",
            }
        ]
    }

    from unittest.mock import MagicMock
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_resp
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        results = await service.search_employees("Wonderland Inc", ["CTO"])
        assert len(results) == 1
        assert results[0]["name"] == "Alice Wonderland"
        assert results[0]["title"] == "Chief Technology Officer"
        assert results[0]["linkedin_url"] == "https://linkedin.com/in/alicewonderland"
        assert results[0]["source"] == "coresignal"

        # Check call arguments
        call_args = mock_post.call_args
        assert call_args.kwargs["headers"]["apikey"] == "test_cs_key"
        assert call_args.kwargs["json"]["entity"] == "employee"
        assert call_args.kwargs["json"]["return_data"] is True
        assert call_args.kwargs["json"]["threshold"] == 0.97


@pytest.mark.asyncio
async def test_contact_enrichment_with_coresignal():
    mock_cs = MockCoresignalService()
    agent = ContactEnrichmentAgent(coresignal_service=mock_cs)

    decision_maker = {
        "name": "Jane Doe",
        "company": "Acme Inc",
        "domain": "acme.com",
        "title": "VP of Engineering",
        "linkedin_url": "linkedin.com/in/janedoe",
        "user_id": "test_user",
        "workflow_id": "test_wf",
    }

    with patch("app.agents.contact_enrichment_agent.get_cached", AsyncMock(side_effect=Exception("Redis down"))), \
         patch("app.agents.contact_enrichment_agent.set_cached", AsyncMock(side_effect=Exception("Redis down"))):
        enriched = await agent._enrich_one(decision_maker)
        assert enriched["name"] == "Jane Doe"
        assert enriched["linkedin_url"].startswith("https://")
