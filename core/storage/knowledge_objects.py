from __future__ import annotations

import asyncio
import importlib
import os
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

from core.runtime.env import is_protected_environment


class KnowledgeStorageConfigurationError(RuntimeError):
    pass


class KnowledgeObjectStore(Protocol):
    async def put(
        self, tenant_id: UUID, content: bytes, *, suffix: str = ""
    ) -> str: ...
    async def read(self, reference: str) -> bytes: ...
    async def delete(self, reference: str) -> None: ...


class LocalKnowledgeObjectStore:
    def __init__(self, root: str | Path, *, max_bytes: int = 20 * 1024 * 1024) -> None:
        self.root = Path(root).resolve()
        self.max_bytes = max_bytes

    def _resolve(self, reference: str) -> Path:
        if not reference.startswith("local://"):
            raise ValueError("Unsupported local object reference.")
        path = (self.root / reference.removeprefix("local://")).resolve()
        if self.root not in path.parents:
            raise PermissionError("Object reference escapes the storage root.")
        return path

    async def put(self, tenant_id: UUID, content: bytes, *, suffix: str = "") -> str:
        if len(content) > self.max_bytes:
            raise ValueError("Object exceeds storage limit.")
        safe_suffix = suffix.casefold() if suffix and suffix[1:].isalnum() else ""
        relative = Path(str(tenant_id)) / f"{uuid4().hex}{safe_suffix}"
        target = (self.root / relative).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        await asyncio.to_thread(temporary.write_bytes, content)
        await asyncio.to_thread(temporary.replace, target)
        return f"local://{relative.as_posix()}"

    async def read(self, reference: str) -> bytes:
        return await asyncio.to_thread(self._resolve(reference).read_bytes)

    async def delete(self, reference: str) -> None:
        path = self._resolve(reference)
        try:
            await asyncio.to_thread(path.unlink)
        except FileNotFoundError:
            pass


class S3KnowledgeObjectStore:
    def __init__(
        self, bucket: str, *, endpoint_url: str | None = None, prefix: str = "knowledge"
    ) -> None:
        if not bucket.strip():
            raise KnowledgeStorageConfigurationError(
                "Knowledge object bucket is required."
            )
        try:
            boto3 = importlib.import_module("boto3")
        except ImportError as exc:
            raise KnowledgeStorageConfigurationError(
                "Install the knowledge-s3 extra for S3 object storage."
            ) from exc

        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.client = boto3.client("s3", endpoint_url=endpoint_url)

    async def put(self, tenant_id: UUID, content: bytes, *, suffix: str = "") -> str:
        safe_suffix = suffix.casefold() if suffix and suffix[1:].isalnum() else ""
        key = f"{self.prefix}/{tenant_id}/{uuid4().hex}{safe_suffix}"
        await asyncio.to_thread(
            self.client.put_object, Bucket=self.bucket, Key=key, Body=content
        )
        return f"s3://{self.bucket}/{key}"

    def _key(self, reference: str) -> str:
        prefix = f"s3://{self.bucket}/"
        if not reference.startswith(prefix):
            raise ValueError("Object reference belongs to another bucket.")
        return reference.removeprefix(prefix)

    async def read(self, reference: str) -> bytes:
        response = await asyncio.to_thread(
            self.client.get_object, Bucket=self.bucket, Key=self._key(reference)
        )
        return await asyncio.to_thread(response["Body"].read)

    async def delete(self, reference: str) -> None:
        await asyncio.to_thread(
            self.client.delete_object, Bucket=self.bucket, Key=self._key(reference)
        )


_default_store: KnowledgeObjectStore | None = None


def get_default_knowledge_object_store() -> KnowledgeObjectStore:
    global _default_store
    if _default_store is not None:
        return _default_store
    bucket = (os.environ.get("UCVE_KNOWLEDGE_S3_BUCKET") or "").strip()
    if bucket:
        _default_store = S3KnowledgeObjectStore(
            bucket, endpoint_url=os.environ.get("UCVE_KNOWLEDGE_S3_ENDPOINT")
        )
    elif is_protected_environment():
        raise KnowledgeStorageConfigurationError(
            "Protected environments require durable knowledge object storage."
        )
    else:
        root = os.environ.get(
            "UCVE_KNOWLEDGE_LOCAL_ROOT", "hamza_local/knowledge_objects"
        )
        _default_store = LocalKnowledgeObjectStore(root)
    return _default_store


def reset_default_knowledge_object_store() -> None:
    global _default_store
    _default_store = None
