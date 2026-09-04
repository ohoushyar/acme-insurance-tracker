"""Renewal reminder threshold helpers."""

from __future__ import annotations

from datetime import UTC, date, datetime

REMINDER_THRESHOLDS = (60, 30, 10)


def utc_today() -> date:
    return datetime.now(UTC).date()


def due_thresholds(renewal_date: date | None, today: date) -> list[int]:
    if renewal_date is None:
        return []
    days = (renewal_date - today).days
    if days < 1:
        return []
    return [threshold for threshold in REMINDER_THRESHOLDS if days <= threshold]
