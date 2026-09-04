from datetime import date, timedelta

from app.reminders import due_thresholds


def test_due_thresholds_at_boundaries() -> None:
    today = date(2026, 9, 3)
    assert due_thresholds(today + timedelta(days=61), today) == []
    assert due_thresholds(today + timedelta(days=60), today) == [60]
    assert due_thresholds(today + timedelta(days=45), today) == [60]
    assert due_thresholds(today + timedelta(days=30), today) == [60, 30]
    assert due_thresholds(today + timedelta(days=10), today) == [60, 30, 10]
    assert due_thresholds(today + timedelta(days=1), today) == [60, 30, 10]


def test_due_thresholds_skip_today_overdue_and_missing() -> None:
    today = date(2026, 9, 3)
    assert due_thresholds(today, today) == []
    assert due_thresholds(today - timedelta(days=1), today) == []
    assert due_thresholds(None, today) == []
