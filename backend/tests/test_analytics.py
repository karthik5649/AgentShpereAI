import pytest
from app.memory.document_store import create_workflow, log_agent_event


@pytest.mark.asyncio
async def test_get_analytics_endpoint(client, fake_db):
    # Create test workflows
    await create_workflow({
        "user_id": "user_test",
        "name": "Campaign A",
        "status": "completed",
        "results_count": 10,
        "total_cost_usd": 1.50,
        "total_tokens": 12000,
    })
    await create_workflow({
        "user_id": "user_test",
        "name": "Campaign B",
        "status": "completed",
        "results_count": 5,
        "total_cost_usd": 0.75,
        "total_tokens": 6000,
    })

    # Log some agent activity
    await log_agent_event({
        "workflow_id": "wf_1",
        "user_id": "user_test",
        "agent_name": "company_discovery_agent",
        "action": "discovered_companies",
        "cost_usd": 0.50,
        "tokens": 4000,
    })
    await log_agent_event({
        "workflow_id": "wf_1",
        "user_id": "user_test",
        "agent_name": "summary_agent",
        "action": "generated_summary",
        "cost_usd": 0.80,
        "tokens": 7000,
    })

    res = client.get("/api/v1/analytics")
    assert res.status_code == 200
    data = res.json()

    assert data["total_workflows"] == 2
    assert data["total_cost_usd"] == 2.25
    assert data["total_tokens"] == 18000
    assert data["total_leads"] == 15
    assert data["cost_per_lead"] == round(2.25 / 15, 4)
    assert len(data["daily_spend"]) == 7
    assert len(data["agent_breakdown"]) >= 2
