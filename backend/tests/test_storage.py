from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.config import Settings
from app.storage import (
    InMemoryDocumentStore,
    S3DocumentStore,
    StorageKeyError,
    assert_owned_storage_key,
    build_document_store,
    document_storage_key,
    is_aws_s3_endpoint,
    s3_addressing_style,
)


def _settings(**overrides: str) -> Settings:
    values: dict[str, str] = {
        "database_url": "postgresql+asyncpg://app:app@localhost:5432/insurance",
        "redis_url": "redis://localhost:6379/0",
        "s3_endpoint": "",
        "s3_bucket": "insurance-docs",
        "s3_access_key": "",
        "s3_secret_key": "",
        "s3_region": "us-east-1",
    }
    values.update(overrides)
    return Settings(**values)


def test_storage_key_is_user_id_slash_document_id_pdf() -> None:
    user_id = uuid4()
    document_id = uuid4()
    assert document_storage_key(user_id, document_id) == f"{user_id}/{document_id}.pdf"


def test_owned_storage_key_is_accepted() -> None:
    user_id = uuid4()
    document_id = uuid4()
    assert_owned_storage_key(user_id, document_storage_key(user_id, document_id))


def test_storage_key_for_another_user_is_rejected() -> None:
    user_a = uuid4()
    user_b = uuid4()
    foreign_key = document_storage_key(user_b, uuid4())
    with pytest.raises(StorageKeyError):
        assert_owned_storage_key(user_a, foreign_key)


async def test_in_memory_store_put_and_get_round_trip() -> None:
    store = InMemoryDocumentStore()
    key = document_storage_key(uuid4(), uuid4())
    body = b"%PDF-1.4\n%%EOF\n"
    await store.put_pdf(key, body)
    assert await store.get_pdf(key) == body


async def test_s3_store_reads_and_writes_constructed_key_only() -> None:
    from unittest.mock import MagicMock

    client = MagicMock()
    body_stream = MagicMock()
    body_stream.read.return_value = b"%PDF-1.4\n%%EOF\n"
    client.get_object.return_value = {"Body": body_stream}
    store = S3DocumentStore(
        endpoint_url="http://localhost:9000",
        bucket="insurance-docs",
        access_key="test",
        secret_key="test",
        client=client,
    )
    key = document_storage_key(uuid4(), uuid4())
    await store.put_pdf(key, b"%PDF-1.4\n%%EOF\n")
    client.put_object.assert_called_once()
    put_kwargs = client.put_object.call_args.kwargs
    assert put_kwargs["Bucket"] == "insurance-docs"
    assert put_kwargs["Key"] == key
    assert not key.startswith("/")
    assert client.list_objects_v2.call_count == 0
    assert client.list_objects.call_count == 0

    assert await store.get_pdf(key) == b"%PDF-1.4\n%%EOF\n"
    get_kwargs = client.get_object.call_args.kwargs
    assert get_kwargs["Bucket"] == "insurance-docs"
    assert get_kwargs["Key"] == key


async def test_s3_missing_key_raises_file_not_found() -> None:
    from unittest.mock import MagicMock

    from botocore.exceptions import ClientError

    client = MagicMock()
    client.get_object.side_effect = ClientError(
        {
            "Error": {
                "Code": "NoSuchKey",
                "Message": "The specified key does not exist.",
            },
            "ResponseMetadata": {"HTTPStatusCode": 404},
        },
        "GetObject",
    )
    store = S3DocumentStore(
        endpoint_url="http://localhost:9000",
        bucket="insurance-docs",
        access_key="test",
        secret_key="test",
        client=client,
    )
    with pytest.raises(FileNotFoundError):
        await store.get_pdf(document_storage_key(uuid4(), uuid4()))


def test_empty_endpoint_builds_in_memory_store() -> None:
    store = build_document_store(_settings(s3_endpoint=""))
    assert isinstance(store, InMemoryDocumentStore)


def test_aws_s3_endpoint_detection() -> None:
    assert is_aws_s3_endpoint("https://s3.us-east-1.amazonaws.com")
    assert is_aws_s3_endpoint("https://s3.amazonaws.com")
    assert not is_aws_s3_endpoint("http://minio:9000")
    assert not is_aws_s3_endpoint("http://127.0.0.1:9000")
    assert not is_aws_s3_endpoint("")
    assert s3_addressing_style("https://s3.us-east-1.amazonaws.com") == "virtual"
    assert s3_addressing_style("http://minio:9000") == "path"


def test_aws_endpoint_without_keys_uses_default_credential_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_client(service_name: str, **kwargs: object) -> MagicMock:
        assert service_name == "s3"
        captured.update(kwargs)
        return MagicMock()

    monkeypatch.setattr("app.storage.boto3.client", fake_client)
    store = build_document_store(
        _settings(
            s3_endpoint="https://s3.us-east-1.amazonaws.com",
            s3_access_key="",
            s3_secret_key="",
        )
    )
    assert isinstance(store, S3DocumentStore)
    assert "aws_access_key_id" not in captured
    assert "aws_secret_access_key" not in captured
    assert captured.get("endpoint_url") == "https://s3.us-east-1.amazonaws.com"
    config = captured["config"]
    assert config.s3["addressing_style"] == "virtual"


def test_minio_endpoint_uses_path_style_and_static_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_client(service_name: str, **kwargs: object) -> MagicMock:
        assert service_name == "s3"
        captured.update(kwargs)
        return MagicMock()

    monkeypatch.setattr("app.storage.boto3.client", fake_client)
    store = build_document_store(
        _settings(
            s3_endpoint="http://minio:9000",
            s3_access_key="minioadmin",
            s3_secret_key="minioadmin",
        )
    )
    assert isinstance(store, S3DocumentStore)
    assert captured["aws_access_key_id"] == "minioadmin"
    assert captured["aws_secret_access_key"] == "minioadmin"
    assert captured.get("endpoint_url") == "http://minio:9000"
    config = captured["config"]
    assert config.s3["addressing_style"] == "path"
