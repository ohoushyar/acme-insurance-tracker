from decimal import Decimal
from uuid import uuid4

from app.models import Policy
from app.yoy import (
    history_points,
    normalize_coverage_type,
    policy_year,
    previous_premium_for,
    suggest_link_ids,
    yoy_change_pct,
    yoy_flagged,
)


def _policy(**overrides) -> Policy:
    policy = Policy(
        id=uuid4(),
        user_id=uuid4(),
        source_document_id=uuid4(),
        carriers=[],
        deductibles=[],
        locations=[],
        extraction_confidence={},
    )
    for key, value in overrides.items():
        setattr(policy, key, value)
    return policy


def test_policy_year_prefers_effective_date() -> None:
    from datetime import date

    policy = _policy(effective_date=date(2024, 1, 1), renewal_date=date(2025, 1, 1))
    assert policy_year(policy) == 2024
    assert (
        policy_year(_policy(effective_date=None, renewal_date=date(2025, 1, 1))) == 2024
    )
    assert policy_year(_policy(effective_date=None, renewal_date=None)) is None


def test_yoy_change_and_flag_at_ten_percent() -> None:
    assert yoy_change_pct(Decimal(110), Decimal(100)) == 10.0
    assert yoy_flagged(10.0) is True
    assert yoy_flagged(9.9) is False
    assert yoy_change_pct(Decimal(100), Decimal(0)) is None
    assert yoy_change_pct(None, Decimal(100)) is None


def test_previous_premium_from_series_members() -> None:
    from datetime import date

    older = _policy(effective_date=date(2023, 1, 1), total_premium=Decimal(10000))
    newer = _policy(effective_date=date(2024, 1, 1), total_premium=Decimal(12000))
    assert previous_premium_for(newer, [older, newer]) == Decimal(10000)
    assert history_points([newer, older])[0]["year"] == 2023


def test_suggest_links_requires_shared_property_and_coverage() -> None:
    prop_a = uuid4()
    prop_b = uuid4()
    current = _policy(coverage_type="Property")
    match = _policy(coverage_type=" property ")
    wrong_coverage = _policy(coverage_type="Flood")
    no_overlap = _policy(coverage_type="Property")
    ids = suggest_link_ids(
        current,
        {prop_a},
        [
            (match, {prop_a}),
            (wrong_coverage, {prop_a}),
            (no_overlap, {prop_b}),
        ],
    )
    assert ids == [match.id]
    assert normalize_coverage_type("  Property  ") == "property"
