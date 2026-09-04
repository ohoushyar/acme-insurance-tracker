from __future__ import annotations

import asyncio
from typing import Any, Protocol
from urllib.parse import urlparse
from uuid import UUID

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import Settings


class StorageKeyError(ValueError):
    """Raised when a storage key is not owned by the expected user."""


class DocumentStore(Protocol):
    async def put_pdf(
        self, key: str, body: bytes, content_type: str = "application/pdf"
    ) -> None: ...

    async def get_pdf(self, key: str) -> bytes: ...


def document_storage_key(user_id: UUID | str, document_id: UUID | str) -> str:
    return f"{user_id}/{document_id}.pdf"


def assert_owned_storage_key(user_id: UUID | str, storage_key: str) -> None:
    prefix = f"{user_id}/"
    if not storage_key.startswith(prefix):
        raise StorageKeyError("storage key is not owned by this user")


class InMemoryDocumentStore:
    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    async def put_pdf(
        self, key: str, body: bytes, content_type: str = "application/pdf"
    ) -> None:
        _ = content_type
        self._objects[key] = body

    async def get_pdf(self, key: str) -> bytes:
        try:
            return self._objects[key]
        except KeyError as exc:
            raise FileNotFoundError(key) from exc


def is_aws_s3_endpoint(endpoint_url: str) -> bool:
    if not endpoint_url:
        return False
    host = (urlparse(endpoint_url).hostname or "").lower()
    if host == "s3.amazonaws.com":
        return True
    return host.endswith(".amazonaws.com") and host.startswith(("s3.", "s3-"))


def s3_addressing_style(endpoint_url: str) -> str:
    return "virtual" if is_aws_s3_endpoint(endpoint_url) else "path"


def _is_missing_s3_object(exc: ClientError) -> bool:
    error = exc.response.get("Error") or {}
    code = str(error.get("Code", ""))
    http_status = (exc.response.get("ResponseMetadata") or {}).get("HTTPStatusCode")
    return code in {"NoSuchKey", "NotFound", "404"} or http_status == 404


class S3DocumentStore:
    def __init__(
        self,
        *,
        endpoint_url: str,
        bucket: str,
        access_key: str = "",
        secret_key: str = "",
        region: str = "us-east-1",
        client: BaseClient | None = None,
    ) -> None:
        self._bucket = bucket
        client_kwargs: dict[str, Any] = {
            "endpoint_url": endpoint_url,
            "region_name": region,
            "config": Config(
                signature_version="s3v4",
                s3={"addressing_style": s3_addressing_style(endpoint_url)},
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        }
        if access_key and secret_key:
            client_kwargs["aws_access_key_id"] = access_key
            client_kwargs["aws_secret_access_key"] = secret_key
        self._client = client or boto3.client("s3", **client_kwargs)

    async def put_pdf(
        self, key: str, body: bytes, content_type: str = "application/pdf"
    ) -> None:
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
        )

    async def get_pdf(self, key: str) -> bytes:
        def _get() -> bytes:
            try:
                response = self._client.get_object(Bucket=self._bucket, Key=key)
            except ClientError as exc:
                if _is_missing_s3_object(exc):
                    raise FileNotFoundError(key) from exc
                raise
            return response["Body"].read()

        return await asyncio.to_thread(_get)


def build_document_store(settings: Settings) -> InMemoryDocumentStore | S3DocumentStore:
    if not settings.s3_endpoint:
        return InMemoryDocumentStore()
    return S3DocumentStore(
        endpoint_url=settings.s3_endpoint,
        bucket=settings.s3_bucket,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        region=settings.s3_region,
    )
