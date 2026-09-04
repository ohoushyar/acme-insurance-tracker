import pytest


def test_extract_document_time_limit_marks_failed_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dramatiq.middleware.time_limit import TimeLimitExceeded

    from app.queue import actors as actors_mod

    persisted: dict[str, object] = {}

    async def boom(document_id: str, user_id: str) -> None:
        raise TimeLimitExceeded()

    async def persist(
        document_id: str,
        user_id: str,
        *,
        status: str,
        extracted: dict | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        persisted["document_id"] = document_id
        persisted["user_id"] = user_id
        persisted["status"] = status
        persisted["error_code"] = error_code
        persisted["error_message"] = error_message

    monkeypatch.setattr(actors_mod, "_extract_document", boom)
    monkeypatch.setattr(actors_mod, "_persist_status", persist)

    actors_mod.extract_document("doc-1", "user-1")

    assert persisted["document_id"] == "doc-1"
    assert persisted["status"] == "failed"
    assert persisted["error_code"] == "EXTRACTION_FAILED"
    assert "time" in str(persisted["error_message"]).lower()
