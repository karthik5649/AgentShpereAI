import pytest
from app.services.eval_service import evaluate_dataset, load_labeled_fixture_dataset


def test_load_labeled_fixture_dataset():
    dataset = load_labeled_fixture_dataset()
    assert len(dataset) == 15
    qualified = [c for c in dataset if c.get("ground_truth")]
    unqualified = [c for c in dataset if not c.get("ground_truth")]
    assert len(qualified) == 8
    assert len(unqualified) == 7


def test_evaluate_dataset_metrics():
    metrics = evaluate_dataset()
    assert metrics["total_samples"] == 15
    assert metrics["precision"] >= 0.80
    assert metrics["recall"] >= 0.80
    assert metrics["accuracy"] >= 0.80
    assert metrics["f1_score"] >= 0.80
    assert len(metrics["details"]) == 15


def test_eval_run_endpoint_default(client):
    res = client.post("/api/v1/eval/run", json={})
    assert res.status_code == 200
    data = res.json()
    assert data["total_samples"] == 15
    assert data["precision"] >= 0.80
    assert data["recall"] >= 0.80
    assert data["accuracy"] >= 0.80
    assert data["true_positives"] >= 7
    assert data["true_negatives"] >= 6


def test_eval_run_endpoint_custom_dataset(client):
    custom_companies = [
        {
            "name": "Target Tech",
            "domain": "targettech.io",
            "industry": "B2B SaaS",
            "headcount": 100,
            "funding_stage": "Series A",
            "geography": "United States",
            "ground_truth": True,
        },
        {
            "name": "Off Target Tech",
            "domain": "offtarget.io",
            "industry": "Construction",
            "headcount": 10,
            "funding_stage": "Seed",
            "geography": "Australia",
            "ground_truth": False,
        },
    ]

    res = client.post("/api/v1/eval/run", json={"companies": custom_companies})
    assert res.status_code == 200
    data = res.json()
    assert data["total_samples"] == 2
    assert data["accuracy"] == 1.0
    assert data["true_positives"] == 1
    assert data["true_negatives"] == 1
