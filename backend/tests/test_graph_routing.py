import pytest

from app.core.config import get_settings
from app.graph.workflow_graph import build_workflow_graph, route_after_validation
from app.memory.vector_store import init_vector_store
from app.services.workflow_executor import run_workflow_async as _run_workflow_async


def test_route_after_validation_logic():
    # Empty validated companies -> unqualified
    assert route_after_validation({"validated_companies": []}) == "unqualified"

    # Qualified company exists -> qualified
    assert (
        route_after_validation(
            {"validated_companies": [{"name": "A", "icp_status": "qualified"}]}
        )
        == "qualified"
    )

    # Only uncertain companies -> uncertain
    assert (
        route_after_validation(
            {"validated_companies": [{"name": "B", "icp_status": "uncertain"}]}
        )
        == "uncertain"
    )

    # Only unqualified companies -> unqualified
    assert (
        route_after_validation(
            {"validated_companies": [{"name": "C", "icp_status": "unqualified"}]}
        )
        == "unqualified"
    )


@pytest.mark.asyncio
async def test_graph_skips_enrichment_when_unqualified(fake_db, fake_redis, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "MOCK_MODE", True)
    monkeypatch.setattr(settings, "SERPER_API_KEY", None)
    monkeypatch.setattr(settings, "HUNTER_API_KEY", None)
    monkeypatch.setattr(settings, "APOLLO_API_KEY", None)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)

    init_vector_store(None, ":memory:")

    workflow_id = "wf_routing_unqualified"
    await fake_db.workflows.insert_one({
        "_id": workflow_id,
        "user_id": "user_routing",
        "session_id": "sess_routing",
        "name": "Unqualified Routing Test",
        "status": "pending",
        "created_at": "2024-01-01T00:00:00Z",
    })

    # Impossible criteria for B2B SaaS companies: Healthcare industry with 50,000+ headcount
    workflow_config = {
        "workflow_id": workflow_id,
        "session_id": "sess_routing",
        "user_id": "user_routing",
        "icp": {
            "industry": ["Aerospace & Defense"],
            "headcount_min": 50000,
            "headcount_max": 100000,
            "funding_stages": ["Series Z"],
            "geography": ["Antarctica"],
            "min_icp_score": 0.0,  # allow all through discovery so validation evaluates them as unqualified
        },
        "personas": [
            {"name": "Economic Buyer", "titles": ["VP Sales"], "priority": 1}
        ],
        "triggers": ["funding_round"],
    }

    result = await _run_workflow_async(
        workflow_id,
        workflow_config,
        redis=fake_redis,
        db=fake_db,
    )

    assert result["status"] in {"pending", "awaiting_approval", "completed"}
    assert len(result.get("enriched_contacts", [])) == 0
    assert result.get("summary_report") is not None
