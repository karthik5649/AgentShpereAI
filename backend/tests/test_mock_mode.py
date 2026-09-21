import pytest

from app.core.config import get_settings
from app.memory.vector_store import init_vector_store
from app.services.workflow_executor import run_workflow_async as _run_workflow_async


@pytest.mark.asyncio
async def test_mock_mode_workflow_execution(fake_db, fake_redis, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "MOCK_MODE", True)
    monkeypatch.setattr(settings, "SERPER_API_KEY", None)
    monkeypatch.setattr(settings, "HUNTER_API_KEY", None)
    monkeypatch.setattr(settings, "APOLLO_API_KEY", None)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)

    init_vector_store(None, ":memory:")

    workflow_id = "wf_mock_test_1"
    await fake_db.workflows.insert_one({
        "_id": workflow_id,
        "user_id": "user_mock",
        "session_id": "sess_mock_test_1",
        "name": "Mock Test Workflow",
        "status": "pending",
        "created_at": "2024-01-01T00:00:00Z",
    })

    workflow_config = {
        "workflow_id": workflow_id,
        "session_id": "sess_mock_test_1",
        "user_id": "user_mock",
        "icp": {
            "industry": ["B2B SaaS"],
            "headcount_min": 20,
            "headcount_max": 500,
            "funding_stages": ["Series A", "Series B"],
            "geography": ["United States"],
        },
        "personas": [
            {"name": "Economic Buyer", "titles": ["VP Sales", "Chief Revenue Officer"], "priority": 1}
        ],
        "triggers": ["funding_round"],
    }

    result = await _run_workflow_async(
        workflow_id,
        workflow_config,
        redis=fake_redis,
        db=fake_db,
    )

    assert len(result.get("discovered_companies", [])) > 0
    assert len(result.get("validated_companies", [])) > 0
    assert len(result.get("enriched_contacts", [])) > 0
    assert result.get("summary_report") is not None
    assert result.get("status") in {"pending", "awaiting_approval"}

    workflow = await fake_db.workflows.find_one({"_id": workflow_id})
    assert workflow is not None
    assert workflow.get("status") == "awaiting_approval"
    assert workflow.get("results_count", 0) > 0
