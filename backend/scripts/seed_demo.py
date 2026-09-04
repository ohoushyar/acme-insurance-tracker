"""Load synthetic demo portfolios into the local database. Dev only."""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import structlog
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings
from app.extraction.schema import ExtractedPolicy, FieldConfidence
from app.logging import configure_logging
from app.models import (
    Document,
    Policy,
    PolicyProperty,
    PolicySeries,
    Property,
    Reminder,
    User,
)
from app.policy_mapping import apply_extracted
from app.security import hash_password
from app.storage import build_document_store, document_storage_key

DEMO_PASSWORD = "demo-pass-1"
FIXTURE_PATH = BACKEND_ROOT / "fixtures" / "demo_portfolios.json"
LOCAL_HOST_MARKERS = ("localhost", "127.0.0.1", "@postgres:")

log = structlog.get_logger("seed_demo")


def _tiny_pdf() -> bytes:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _assert_local_database(url: str) -> None:
    lowered = url.lower()
    if any(marker in lowered for marker in LOCAL_HOST_MARKERS):
        return
    raise SystemExit(
        "Refusing to seed a non-local database. "
        "ADMIN_DATABASE_URL must point at localhost, 127.0.0.1, or Compose 'postgres'."
    )


def utc_today() -> date:
    return datetime.now(UTC).date()


def _confidence(overrides: dict[str, Any] | None) -> dict[str, float]:
    values = {name: 0.9 for name in FieldConfidence.model_fields}
    if overrides:
        values.update({key: float(value) for key, value in overrides.items()})
    return values


def _effective_for_offset(today: date, offset_days: int) -> date:
    renewal = today + timedelta(days=offset_days)
    try:
        return renewal.replace(year=renewal.year - 1)
    except ValueError:
        return renewal - timedelta(days=365)


def _build_extracted(
    raw: dict[str, Any],
    *,
    today: date,
    default_named_insured: str,
    key: str,
) -> ExtractedPolicy:
    payload = dict(raw)
    offset = payload.pop("renewal_offset_days", None)
    payload.pop("property_labels", None)
    payload.pop("series", None)
    payload.pop("key", None)
    payload.pop("filename", None)
    if "renewal_date" not in payload:
        if offset is None:
            payload["renewal_date"] = None
        else:
            payload["renewal_date"] = today + timedelta(days=int(offset))
    if payload.get("effective_date") in (None, "") and offset is not None:
        payload["effective_date"] = _effective_for_offset(today, int(offset))
    payload.setdefault("named_insured", default_named_insured)
    payload.setdefault("broker", "Northshore Risk Partners")
    payload.setdefault("policy_number", f"DEMO-{key.upper()}")
    payload.setdefault("coverage_type", "Property")
    payload.setdefault("carriers", ["Liberty Mutual"])
    payload.setdefault("deductibles", [])
    payload.setdefault("locations", [])
    payload.setdefault("policy_fee", "0")
    if payload.get("term_premium") in (None, "") and payload.get("total_premium"):
        payload["term_premium"] = payload["total_premium"]
    payload["confidence"] = _confidence(payload.get("confidence"))
    return ExtractedPolicy.model_validate(payload)


async def _wipe_demo_users(session: AsyncSession, emails: list[str]) -> None:
    result = await session.execute(select(User).where(User.email.in_(emails)))
    users = list(result.scalars().all())
    if not users:
        return
    user_ids = [user.id for user in users]
    await session.execute(delete(Reminder).where(Reminder.user_id.in_(user_ids)))
    await session.execute(
        delete(PolicyProperty).where(PolicyProperty.user_id.in_(user_ids))
    )
    await session.execute(
        update(Policy).where(Policy.user_id.in_(user_ids)).values(series_id=None)
    )
    await session.execute(delete(Policy).where(Policy.user_id.in_(user_ids)))
    await session.execute(
        delete(PolicySeries).where(PolicySeries.user_id.in_(user_ids))
    )
    await session.execute(delete(Document).where(Document.user_id.in_(user_ids)))
    await session.execute(delete(Property).where(Property.user_id.in_(user_ids)))
    await session.execute(delete(User).where(User.id.in_(user_ids)))


async def _put_pdf(settings: Any, key: str, body: bytes) -> None:
    try:
        store = build_document_store(settings)
        await store.put_pdf(key, body)
    except (BotoCoreError, ClientError, OSError, ConnectionError):
        log.warning("demo_pdf_upload_skipped", storage_key=key)


async def _add_document(
    session: AsyncSession,
    *,
    settings: Any,
    user_id: UUID,
    filename: str,
    status: str,
    extracted: dict[str, Any] | None,
    error_code: str | None,
    error_message: str | None,
    pdf_bytes: bytes,
) -> Document:
    document_id = uuid4()
    storage_key = document_storage_key(user_id, document_id)
    document = Document(
        id=document_id,
        user_id=user_id,
        original_filename=filename,
        content_type="application/pdf",
        byte_size=len(pdf_bytes),
        storage_key=storage_key,
        status=status,
        extracted=extracted,
        error_code=error_code,
        error_message=error_message,
    )
    session.add(document)
    await session.flush()
    await _put_pdf(settings, storage_key, pdf_bytes)
    return document


async def seed() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    if not settings.admin_database_url:
        raise SystemExit("ADMIN_DATABASE_URL is required to seed demo data.")
    _assert_local_database(settings.admin_database_url)
    payload = json.loads(FIXTURE_PATH.read_text())
    users_data: list[dict[str, Any]] = payload["users"]
    emails = [item["email"] for item in users_data]
    today = utc_today()
    pdf_bytes = _tiny_pdf()
    password_hash = hash_password(DEMO_PASSWORD)

    engine = create_async_engine(settings.admin_database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        await _wipe_demo_users(session, emails)
        for user_data in users_data:
            await _seed_user(
                session,
                settings=settings,
                user_data=user_data,
                password_hash=password_hash,
                today=today,
                pdf_bytes=pdf_bytes,
            )
    await engine.dispose()
    log.info("demo_seed_complete", users=len(emails), emails=emails)


async def _seed_user(
    session: AsyncSession,
    *,
    settings: Any,
    user_data: dict[str, Any],
    password_hash: str,
    today: date,
    pdf_bytes: bytes,
) -> None:
    email = user_data["email"].strip().lower()
    named_insured = user_data["named_insured"]
    user = User(id=uuid4(), email=email, password_hash=password_hash)
    session.add(user)
    await session.flush()

    properties_by_label: dict[str, Property] = {}
    for item in user_data.get("properties", []):
        stated = item.get("stated_value")
        prop = Property(
            id=uuid4(),
            user_id=user.id,
            label=item["label"],
            address=item.get("address"),
            stated_value=Decimal(str(stated)) if stated not in (None, "") else None,
        )
        session.add(prop)
        properties_by_label[prop.label] = prop
    await session.flush()

    series_ids: dict[str, UUID] = {}
    for item in user_data.get("series", []):
        series = PolicySeries(
            id=uuid4(),
            user_id=user.id,
            label=item.get("label"),
        )
        session.add(series)
        await session.flush()
        series_ids[item["key"]] = series.id

    for doc_data in user_data.get("documents", []):
        extracted_raw = doc_data.get("extracted")
        extracted = None
        if extracted_raw is not None:
            extracted = ExtractedPolicy.model_validate(extracted_raw).model_dump(
                mode="json"
            )
        await _add_document(
            session,
            settings=settings,
            user_id=user.id,
            filename=doc_data.get("original_filename", "policy.pdf"),
            status=doc_data["status"],
            extracted=extracted,
            error_code=doc_data.get("error_code"),
            error_message=doc_data.get("error_message"),
            pdf_bytes=pdf_bytes,
        )

    for index, policy_data in enumerate(user_data.get("policies", []), start=1):
        key = str(policy_data.get("key") or f"policy-{index}")
        extracted = _build_extracted(
            dict(policy_data),
            today=today,
            default_named_insured=named_insured,
            key=key,
        )
        filename = policy_data.get("filename") or f"{key}.pdf"
        document = await _add_document(
            session,
            settings=settings,
            user_id=user.id,
            filename=filename,
            status="reviewed",
            extracted=extracted.model_dump(mode="json"),
            error_code=None,
            error_message=None,
            pdf_bytes=pdf_bytes,
        )
        series_key = policy_data.get("series")
        series_id = None
        if series_key:
            series_id = series_ids.get(series_key)
            if series_id is None:
                raise SystemExit(f"Unknown series {series_key!r} for {email}")
        policy = Policy(
            id=uuid4(),
            user_id=user.id,
            source_document_id=document.id,
            series_id=series_id,
        )
        apply_extracted(policy, extracted)
        session.add(policy)
        await session.flush()
        for label in policy_data.get("property_labels") or []:
            prop = properties_by_label.get(label)
            if prop is None:
                raise SystemExit(f"Unknown property {label!r} for {email}")
            session.add(
                PolicyProperty(
                    policy_id=policy.id,
                    property_id=prop.id,
                    user_id=user.id,
                )
            )


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
