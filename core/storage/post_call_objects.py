"""Bounded object storage for consented post-call recordings."""

from __future__ import annotations

import asyncio
import importlib
import os
import re
from pathlib import Path, PurePosixPath
from typing import Protocol
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from core.runtime.env import is_protected_environment


class PostCallStorageConfigurationError(RuntimeError):
    pass


class PostCallObjectStore(Protocol):
    async def put(
        self,
        tenant_id: UUID,
        session_id: UUID,
        content: bytes,
        *,
        suffix: str = ".wav",
    ) -> str: ...

    async def read(self, reference: str) -> bytes: ...

    async def delete(self, reference: str) -> bool: ...


class LocalPostCallObjectStore:
    """Tenant-scoped local object store for development and offline tests."""

    _SUFFIX = re.compile(r"^\.[a-z0-9]{1,8}$")

    def __init__(
        self,
        root: str | Path,
        *,
        region: str,
        max_bytes: int = 100 * 1024 * 1024,
    ) -> None:
        self.root = Path(root).resolve()
        self.region = region.strip().casefold()
        self.max_bytes = max_bytes
        if not self.region or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", self.region):
            raise ValueError("A valid storage region is required.")
        if max_bytes < 1:
            raise ValueError("max_bytes must be positive.")

    def _resolve(self, reference: str) -> Path:
        parsed = urlsplit(reference)
        if parsed.scheme != "post-call+local":
            raise ValueError("Unsupported recording object reference.")
        if parsed.netloc.casefold() != self.region:
            raise ValueError("Recording object belongs to another region.")
        relative = PurePosixPath(parsed.path.lstrip("/"))
        if not relative.parts or any(
            part in {"", ".", ".."} for part in relative.parts
        ):
            raise PermissionError("Recording object reference escapes storage root.")
        target = self.root.joinpath(*relative.parts).resolve()
        if target == self.root or self.root not in target.parents:
            raise PermissionError("Recording object reference escapes storage root.")
        return target

    async def put(
        self,
        tenant_id: UUID,
        session_id: UUID,
        content: bytes,
        *,
        suffix: str = ".wav",
    ) -> str:
        if not content:
            raise ValueError("Recording content cannot be empty.")
        if len(content) > self.max_bytes:
            raise ValueError("Recording exceeds the configured storage limit.")
        normalized_suffix = suffix.casefold()
        if not self._SUFFIX.fullmatch(normalized_suffix):
            raise ValueError("Recording suffix is invalid.")
        relative = PurePosixPath(
            str(tenant_id), str(session_id), f"{uuid4().hex}{normalized_suffix}"
        )
        target = self.root.joinpath(*relative.parts).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        await asyncio.to_thread(temporary.write_bytes, bytes(content))
        await asyncio.to_thread(temporary.replace, target)
        return f"post-call+local://{self.region}/{relative.as_posix()}"

    async def read(self, reference: str) -> bytes:
        return await asyncio.to_thread(self._resolve(reference).read_bytes)

    async def delete(self, reference: str) -> bool:
        path = self._resolve(reference)
        try:
            await asyncio.to_thread(path.unlink)
        except FileNotFoundError:
            pass
        return True


class S3PostCallObjectStore:
    """Region-bound S3-compatible storage for consented recordings."""

    _SUFFIX = re.compile(r"^\.[a-z0-9]{1,8}$")

    def __init__(
        self,
        bucket: str,
        *,
        region: str,
        endpoint_url: str | None = None,
        prefix: str = "post-call",
        max_bytes: int = 100 * 1024 * 1024,
    ) -> None:
        self.bucket = bucket.strip()
        self.region = region.strip().casefold()
        self.prefix = prefix.strip("/")
        self.max_bytes = max_bytes
        if not self.bucket or not self.region or not self.prefix:
            raise PostCallStorageConfigurationError(
                "Recording bucket, region, and prefix are required."
            )
        if max_bytes < 1:
            raise ValueError("max_bytes must be positive.")
        try:
            boto3 = importlib.import_module("boto3")
        except ImportError as exc:
            raise PostCallStorageConfigurationError(
                "Install the knowledge-s3 extra for S3 recording storage."
            ) from exc
        self.client = boto3.client(
            "s3", endpoint_url=endpoint_url, region_name=self.region
        )

    def _key(self, reference: str) -> str:
        parsed = urlsplit(reference)
        if parsed.scheme != "post-call+s3" or parsed.netloc != self.region:
            raise ValueError("Recording object belongs to another region.")
        path = PurePosixPath(parsed.path.lstrip("/"))
        if len(path.parts) < 2 or path.parts[0] != self.bucket:
            raise ValueError("Recording object belongs to another bucket.")
        key = PurePosixPath(*path.parts[1:])
        if any(part in {"", ".", ".."} for part in key.parts):
            raise PermissionError("Recording object reference escapes storage prefix.")
        if not key.parts or key.parts[0] != self.prefix:
            raise PermissionError("Recording object reference escapes storage prefix.")
        return key.as_posix()

    async def put(
        self,
        tenant_id: UUID,
        session_id: UUID,
        content: bytes,
        *,
        suffix: str = ".wav",
    ) -> str:
        if not content:
            raise ValueError("Recording content cannot be empty.")
        if len(content) > self.max_bytes:
            raise ValueError("Recording exceeds the configured storage limit.")
        normalized_suffix = suffix.casefold()
        if not self._SUFFIX.fullmatch(normalized_suffix):
            raise ValueError("Recording suffix is invalid.")
        key = f"{self.prefix}/{tenant_id}/{session_id}/{uuid4().hex}{normalized_suffix}"
        await asyncio.to_thread(
            self.client.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=bytes(content),
        )
        return f"post-call+s3://{self.region}/{self.bucket}/{key}"

    async def read(self, reference: str) -> bytes:
        response = await asyncio.to_thread(
            self.client.get_object, Bucket=self.bucket, Key=self._key(reference)
        )
        return await asyncio.to_thread(response["Body"].read)

    async def delete(self, reference: str) -> bool:
        await asyncio.to_thread(
            self.client.delete_object, Bucket=self.bucket, Key=self._key(reference)
        )
        return True


_default_store: PostCallObjectStore | None = None


def get_default_post_call_object_store() -> PostCallObjectStore:
    global _default_store
    if _default_store is not None:
        return _default_store
    bucket = (os.environ.get("UCVE_RECORDING_S3_BUCKET") or "").strip()
    region = (os.environ.get("UCVE_RECORDING_STORAGE_REGION") or "").strip()
    if bucket:
        if not region:
            raise PostCallStorageConfigurationError(
                "UCVE_RECORDING_STORAGE_REGION is required with the S3 bucket."
            )
        _default_store = S3PostCallObjectStore(
            bucket,
            region=region,
            endpoint_url=os.environ.get("UCVE_RECORDING_S3_ENDPOINT"),
        )
    elif is_protected_environment():
        raise PostCallStorageConfigurationError(
            "Protected environments require durable recording object storage."
        )
    else:
        root = os.environ.get(
            "UCVE_RECORDING_LOCAL_ROOT", "hamza_local/post_call_objects"
        )
        _default_store = LocalPostCallObjectStore(root, region=region or "local")
    return _default_store


def reset_default_post_call_object_store() -> None:
    global _default_store
    _default_store = None
