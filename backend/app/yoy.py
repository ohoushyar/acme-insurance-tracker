"""YoY premium helpers and link suggestions."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from app.models import Policy

YOY_FLAG_THRESHOLD = Decimal("0.10")


def normalize_coverage_type(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.strip().lower().split())
    return normalized or None


def policy_year(policy: Policy) -> int | None:
    if policy.effective_date is not None:
        return policy.effective_date.year
    if policy.renewal_date is not None:
        return policy.renewal_date.year - 1
    return None


def yoy_change_pct(current: Decimal | None, previous: Decimal | None) -> float | None:
    if current is None or previous is None:
        return None
    if previous <= 0:
        return None
    return float((current - previous) / previous * Decimal(100))


def yoy_flagged(change_pct: float | None) -> bool:
    if change_pct is None:
        return False
    return Decimal(str(change_pct)) >= YOY_FLAG_THRESHOLD * Decimal(100)


def history_points(members: list[Policy]) -> list[dict]:
    points: list[tuple[int, Policy]] = []
    for member in members:
        year = policy_year(member)
        if year is None:
            continue
        points.append((year, member))
    points.sort(key=lambda item: (item[0], str(item[1].id)))
    result: list[dict] = []
    for year, member in points:
        result.append(
            {
                "year": year,
                "premium": member.total_premium,
                "policy_id": member.id,
            }
        )
    return result


def previous_premium_for(policy: Policy, members: list[Policy]) -> Decimal | None:
    points = history_points(members)
    current_year = policy_year(policy)
    if current_year is None:
        return None
    prior: Decimal | None = None
    for point in points:
        if point["policy_id"] == policy.id:
            return prior
        premium = point["premium"]
        if premium is not None:
            prior = premium
    return None


def suggest_link_ids(
    policy: Policy,
    property_ids: set[UUID],
    candidates: list[tuple[Policy, set[UUID]]],
) -> list[UUID]:
    coverage = normalize_coverage_type(policy.coverage_type)
    if coverage is None or not property_ids:
        return []
    suggestions: list[UUID] = []
    for candidate, candidate_props in candidates:
        if candidate.id == policy.id:
            continue
        if normalize_coverage_type(candidate.coverage_type) != coverage:
            continue
        if property_ids.isdisjoint(candidate_props):
            continue
        suggestions.append(candidate.id)
    return suggestions
