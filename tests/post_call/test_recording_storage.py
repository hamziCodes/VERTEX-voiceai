from __future__ import annotations

from uuid import uuid4

import pytest

from core.storage import post_call_objects
from core.storage.post_call_objects import (
    LocalPostCallObjectStore,
    S3PostCallObjectStore,
)


class _Body:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def read(self) -> bytes:
        return self.content


class _S3Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes) -> None:  # noqa: N803
        self.objects[(Bucket, Key)] = Body

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, _Body]:  # noqa: N803
        return {"Body": _Body(self.objects[(Bucket, Key)])}

    def delete_object(self, *, Bucket: str, Key: str) -> None:  # noqa: N803
        self.objects.pop((Bucket, Key), None)


class _Boto3:
    def __init__(self, client: _S3Client) -> None:
        self._client = client

    def client(self, *_args, **_kwargs) -> _S3Client:
        return self._client


@pytest.mark.asyncio
async def test_local_recording_store_is_tenant_scoped_and_idempotently_deletable(
    tmp_path,
) -> None:
    tenant_id, session_id = uuid4(), uuid4()
    store = LocalPostCallObjectStore(tmp_path, region="pk-isb", max_bytes=32)

    reference = await store.put(
        tenant_id,
        session_id,
        b"recording-bytes",
        suffix=".wav",
    )

    assert reference.startswith("post-call+local://pk-isb/")
    assert await store.read(reference) == b"recording-bytes"
    assert await store.delete(reference) is True
    assert await store.delete(reference) is True
    with pytest.raises(FileNotFoundError):
        await store.read(reference)


@pytest.mark.asyncio
async def test_local_recording_store_rejects_escape_region_and_oversize(
    tmp_path,
) -> None:
    store = LocalPostCallObjectStore(tmp_path, region="pk-isb", max_bytes=4)
    with pytest.raises(ValueError, match="limit"):
        await store.put(uuid4(), uuid4(), b"12345")
    with pytest.raises(ValueError, match="region"):
        await store.delete("post-call+local://eu-west/tenant/session/file.wav")
    with pytest.raises(PermissionError, match="escapes"):
        await store.delete("post-call+local://pk-isb/../../outside.wav")


@pytest.mark.asyncio
async def test_recording_store_rejects_invalid_suffix_and_empty_content(
    tmp_path,
) -> None:
    store = LocalPostCallObjectStore(tmp_path, region="local")
    with pytest.raises(ValueError, match="empty"):
        await store.put(uuid4(), uuid4(), b"")
    with pytest.raises(ValueError, match="suffix"):
        await store.put(uuid4(), uuid4(), b"audio", suffix="../bad")


@pytest.mark.asyncio
async def test_s3_recording_store_enforces_region_bucket_and_prefix(
    monkeypatch,
) -> None:
    client = _S3Client()
    monkeypatch.setattr(
        post_call_objects.importlib,
        "import_module",
        lambda _name: _Boto3(client),
    )
    store = S3PostCallObjectStore("recordings", region="pk-isb")
    reference = await store.put(uuid4(), uuid4(), b"recording")

    assert reference.startswith("post-call+s3://pk-isb/recordings/post-call/")
    assert await store.read(reference) == b"recording"
    with pytest.raises(ValueError, match="region"):
        await store.read(reference.replace("pk-isb", "eu-west", 1))
    with pytest.raises(ValueError, match="bucket"):
        await store.read(reference.replace("/recordings/", "/other/", 1))
    assert await store.delete(reference) is True
