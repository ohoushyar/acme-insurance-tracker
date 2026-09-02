from uuid import uuid4

import pytest

from app.storage import (
    InMemoryDocumentStore,
    S3DocumentStore,
    StorageKeyError,
    assert_owned_storage_key,
    document_storage_key,
)


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
