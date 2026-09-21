import logging
from typing import Any

logger = logging.getLogger("agentsphere.scoring")

CANONICAL_ICP_WEIGHTS: dict[str, float] = {
    "industry": 0.25,
    "headcount": 0.20,
    "funding_stage": 0.20,
    "geography": 0.15,
    "revenue": 0.10,
    "tech_stack": 0.10,
}

GEO_ALIASES: dict[str, list[str]] = {
    "united states": ["usa", "us", "america", "united states of america", "u.s.", "u.s.a."],
    "uk": ["united kingdom", "england", "great britain", "britain"],
    "india": ["in", "bharat"],
    "canada": ["ca"],
    "germany": ["deutschland", "de"],
}


class ICPScoreResult(tuple):
    """4-tuple for backward compatibility with unpack syntax: score, matched, failed, unknown.
    Also exposes .dimension_scores and .score attributes.
    """
    def __new__(cls, score: float, matched: list[str], failed: list[str], unknown: list[str], dimension_scores: dict[str, float] | None = None):
        obj = super().__new__(cls, (score, matched, failed, unknown))
        obj.score = score
        obj.matched = matched
        obj.failed = failed
        obj.unknown = unknown
        obj.dimension_scores = dimension_scores or {}
        return obj


def _get_weight(weights: dict[str, float], dim: str) -> float:
    return float(
        weights.get(dim)
        or weights.get(f"{dim}_match")
        or 0.0
    )


def score_company(
    company: dict[str, Any],
    icp: dict[str, Any],
    weights: dict[str, float] | None = None,
) -> ICPScoreResult:
    """Pure function scoring a company against ICP criteria.

    Returns:
        ICPScoreResult (score, matched_criteria, failed_criteria, unknown_criteria) with .dimension_scores
    Missing information lands in unknown_criteria (score contribution 0.0).
    """
    try:
        effective_weights = weights or icp.get("scoring_weights") or CANONICAL_ICP_WEIGHTS

        matched: list[str] = []
        failed: list[str] = []
        unknown: list[str] = []
        dimension_scores: dict[str, float] = {
            "industry": 0.0,
            "headcount": 0.0,
            "funding_stage": 0.0,
            "geography": 0.0,
            "revenue": 0.0,
            "tech_stack": 0.0,
        }
        total_score: float = 0.0

        # 1. Industry (weight 0.25)
        allowed_industries = icp.get("industry") or []
        val_industry = company.get("industry")
        w_industry = _get_weight(effective_weights, "industry")
        if not allowed_industries:
            matched.append("industry")
            dimension_scores["industry"] = 1.0
            total_score += w_industry
        elif val_industry is None:
            unknown.append("industry")
        else:
            haystack = str(val_industry).lower()
            if any(
                str(item).lower() in haystack or haystack in str(item).lower()
                for item in allowed_industries
            ):
                matched.append("industry")
                dimension_scores["industry"] = 1.0
                total_score += w_industry
            else:
                failed.append("industry")

        # 2. Headcount (weight 0.20)
        h_min = icp.get("headcount_min")
        h_max = icp.get("headcount_max")
        val_headcount = company.get("headcount")
        w_headcount = _get_weight(effective_weights, "headcount")
        if h_min is None and h_max is None:
            matched.append("headcount")
            dimension_scores["headcount"] = 1.0
            total_score += w_headcount
        elif val_headcount is None:
            unknown.append("headcount")
        else:
            try:
                hc_int = int(val_headcount)
                min_bound = int(h_min) if h_min is not None else 0
                max_bound = int(h_max) if h_max is not None else 10**12
                if min_bound <= hc_int <= max_bound:
                    matched.append("headcount")
                    dimension_scores["headcount"] = 1.0
                    total_score += w_headcount
                else:
                    failed.append("headcount")
            except (ValueError, TypeError):
                unknown.append("headcount")

        # 3. Funding Stage (weight 0.20)
        allowed_funding = icp.get("funding_stages") or icp.get("funding_stage") or []
        val_funding = company.get("funding_stage")
        w_funding = _get_weight(effective_weights, "funding_stage")
        if not allowed_funding:
            matched.append("funding_stage")
            dimension_scores["funding_stage"] = 1.0
            total_score += w_funding
        elif val_funding is None:
            unknown.append("funding_stage")
        else:
            haystack = str(val_funding).lower()
            if any(
                str(item).lower() in haystack or haystack in str(item).lower()
                for item in allowed_funding
            ):
                matched.append("funding_stage")
                dimension_scores["funding_stage"] = 1.0
                total_score += w_funding
            else:
                failed.append("funding_stage")

        # 4. Geography (weight 0.15)
        allowed_geos = icp.get("geography") or []
        val_geo = company.get("headquarters") or company.get("geography")
        w_geo = _get_weight(effective_weights, "geography")
        if not allowed_geos:
            matched.append("geography")
            dimension_scores["geography"] = 1.0
            total_score += w_geo
        elif val_geo is None:
            unknown.append("geography")
        else:
            haystack = str(val_geo).lower()
            geo_matched = False
            for allowed in allowed_geos:
                canon = allowed.lower()
                if canon in haystack or haystack in canon:
                    geo_matched = True
                    break
                aliases = GEO_ALIASES.get(canon, [])
                if any(alias in haystack for alias in aliases):
                    geo_matched = True
                    break
                for c_name, a_list in GEO_ALIASES.items():
                    if canon in a_list and (c_name in haystack or any(a in haystack for a in a_list)):
                        geo_matched = True
                        break
            if geo_matched:
                matched.append("geography")
                dimension_scores["geography"] = 1.0
                total_score += w_geo
            else:
                failed.append("geography")

        # 5. Revenue (weight 0.10)
        rev_min = icp.get("revenue_min_usd")
        val_rev = company.get("revenue_estimate_usd") or company.get("revenue")
        w_rev = _get_weight(effective_weights, "revenue")
        if rev_min is None or rev_min == 0:
            matched.append("revenue")
            dimension_scores["revenue"] = 1.0
            total_score += w_rev
        elif val_rev is None:
            unknown.append("revenue")
        else:
            try:
                min_dollars = int(rev_min) * 1_000_000 if int(rev_min) < 10_000 else int(rev_min)
                if int(val_rev) >= min_dollars:
                    matched.append("revenue")
                    dimension_scores["revenue"] = 1.0
                    total_score += w_rev
                else:
                    failed.append("revenue")
            except (ValueError, TypeError):
                unknown.append("revenue")

        # 6. Tech Stack (weight 0.10)
        allowed_tech = icp.get("tech_stack") or []
        val_tech = company.get("tech_stack")
        w_tech = _get_weight(effective_weights, "tech_stack")
        if not allowed_tech:
            matched.append("tech_stack")
            dimension_scores["tech_stack"] = 1.0
            total_score += w_tech
        elif not val_tech:
            unknown.append("tech_stack")
        else:
            tech_set = {str(item).lower() for item in val_tech}
            if any(str(item).lower() in tech_set for item in allowed_tech):
                matched.append("tech_stack")
                dimension_scores["tech_stack"] = 1.0
                total_score += w_tech
            else:
                failed.append("tech_stack")

        final_score = round(total_score, 4)

        # Structured debug logging of dimension-by-dimension evaluation
        logger.debug(
            "icp_scoring_evaluated: company=%s total_score=%.4f matched=%s failed=%s unknown=%s dim_scores=%s",
            company.get("name") or company.get("domain") or "Unknown",
            final_score,
            matched,
            failed,
            unknown,
            dimension_scores,
            extra={
                "company_name": company.get("name"),
                "company_domain": company.get("domain"),
                "total_score": final_score,
                "matched": matched,
                "failed": failed,
                "unknown": unknown,
                "dimension_scores": dimension_scores,
                "inputs": {
                    "industry": company.get("industry"),
                    "headcount": company.get("headcount"),
                    "funding_stage": company.get("funding_stage"),
                    "headquarters": company.get("headquarters"),
                    "revenue": company.get("revenue_estimate_usd") or company.get("revenue"),
                    "tech_stack": company.get("tech_stack"),
                },
            },
        )

        if isinstance(company, dict):
            company["dimension_scores"] = dimension_scores

        return ICPScoreResult(final_score, matched, failed, unknown, dimension_scores)

    except Exception as exc:
        logger.error(
            "icp_scoring_failed for company=%s: %s",
            company.get("name") or company.get("domain") or "Unknown",
            exc,
            exc_info=True,
        )
        if isinstance(company, dict):
            company["scoring_error"] = str(exc)
        return ICPScoreResult(0.0, [], [], ["scoring_exception"], {})


icp_score_company = score_company
