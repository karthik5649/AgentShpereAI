import json
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.icp_scoring_service import CANONICAL_ICP_WEIGHTS, score_company

DEFAULT_REFERENCE_ICP: dict[str, Any] = {
    "industry": ["B2B SaaS", "Enterprise Software", "Cloud Infrastructure"],
    "headcount_min": 50,
    "headcount_max": 1000,
    "funding_stages": ["Series A", "Series B", "Series C", "Growth"],
    "geography": ["United States", "Canada", "United Kingdom"],
    "revenue_min_usd": 5000000,
    "tech_stack": ["AWS", "Kubernetes", "PostgreSQL", "React", "Python"],
}


def load_labeled_fixture_dataset() -> list[dict[str, Any]]:
    fixture_path = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "labeled_companies.json"
    if fixture_path.exists():
        with open(fixture_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def evaluate_dataset(
    companies: list[dict[str, Any]] | None = None,
    icp: dict[str, Any] | None = None,
    weights: dict[str, float] | None = None,
    cutoff: float | None = None,
) -> dict[str, Any]:
    dataset = companies if companies is not None else load_labeled_fixture_dataset()
    eval_icp = icp or DEFAULT_REFERENCE_ICP
    eval_weights = weights or CANONICAL_ICP_WEIGHTS
    eval_cutoff = cutoff if cutoff is not None else getattr(get_settings(), "ICP_QUALIFY_CUTOFF", 0.65)

    total_samples = len(dataset)
    tp = 0
    fp = 0
    tn = 0
    fn = 0
    scores: list[float] = []
    details: list[dict[str, Any]] = []

    for item in dataset:
        score, matched, failed, unknown = score_company(item, eval_icp, eval_weights)
        scores.append(score)
        predicted_qualified = score >= eval_cutoff
        ground_truth = bool(item.get("ground_truth", False))

        if predicted_qualified and ground_truth:
            tp += 1
        elif predicted_qualified and not ground_truth:
            fp += 1
        elif not predicted_qualified and not ground_truth:
            tn += 1
        else:
            fn += 1

        details.append({
            "name": item.get("name"),
            "domain": item.get("domain"),
            "score": score,
            "predicted_qualified": predicted_qualified,
            "ground_truth": ground_truth,
            "matched_criteria": matched,
            "failed_criteria": failed,
            "unknown_criteria": unknown,
        })

    precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
    recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
    f1 = round(2 * (precision * recall) / (precision + recall), 4) if (precision + recall) > 0 else 0.0
    accuracy = round((tp + tn) / total_samples, 4) if total_samples > 0 else 0.0
    mean_score = round(sum(scores) / total_samples, 4) if total_samples > 0 else 0.0

    return {
        "total_samples": total_samples,
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "accuracy": accuracy,
        "mean_score": mean_score,
        "cutoff_used": eval_cutoff,
        "details": details,
    }
