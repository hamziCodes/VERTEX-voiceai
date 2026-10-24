"""Durable, bounded knowledge-source parsing worker."""

from __future__ import annotations

import asyncio
from pathlib import PurePath
from typing import Any, cast
from uuid import UUID

from core.rag.ingestion.chunkers.pdf import chunk_pdf_text
from core.rag.ingestion.chunkers.structured import chunk_structured_document
from core.rag.ingestion.parsers.base import IngestionParseError
from core.rag.ingestion.parsers.registry import parse_document
from core.rag.ingestion.validation import IngestionValidationError, validate_upload
from core.rag.models import ChunkConfig, KnowledgeBaseChunk, KnowledgeBaseSource
from core.storage.knowledge_objects import KnowledgeObjectStore


class IngestionWorker:
    def __init__(
        self,
        repository: Any | None = None,
        object_store: KnowledgeObjectStore | None = None,
        *,
        worker_id: str = "knowledge-worker",
        chunk_config: ChunkConfig | None = None,
        parser_timeout_seconds: float = 30.0,
    ) -> None:
        self.repository = repository
        self.object_store = object_store
        self.worker_id = worker_id
        self.config = chunk_config or ChunkConfig()
        self.parser_timeout_seconds = parser_timeout_seconds

    async def process_next(self) -> UUID | None:
        if self.repository is None or self.object_store is None:
            raise RuntimeError("Durable repository and object store are required.")
        repository = self.repository
        claimed = await _resolve(repository.claim_next_job(self.worker_id))
        if claimed is None:
            return None
        _job, source = claimed
        try:
            content = await self.object_store.read(source.object_reference)
            validated = validate_upload(source.display_name, source.media_type, content)
            if validated.checksum_sha256 != source.checksum_sha256:
                raise IngestionValidationError(
                    "checksum_mismatch", "Stored file integrity check failed."
                )
            document = await asyncio.wait_for(
                asyncio.to_thread(parse_document, validated, content),
                timeout=self.parser_timeout_seconds,
            )
            chunks = chunk_structured_document(
                document,
                tenant_id=source.tenant_id,
                source_id=source.source_id,
                config=self.config,
            )
            if not chunks:
                raise IngestionParseError(
                    "no_extractable_text", "Document contains no extractable text."
                )
            await _resolve(
                repository.store_chunks(
                    source.tenant_id,
                    source.knowledge_base_id,
                    source.source_id,
                    chunks,
                )
            )
        except TimeoutError:
            await self._fail(
                source, "parser_timeout", "Document parsing exceeded the time limit."
            )
        except (IngestionValidationError, IngestionParseError) as exc:
            await self._fail(source, exc.code, exc.safe_message)
        except FileNotFoundError:
            await self._fail(
                source, "object_missing", "Stored source file is unavailable."
            )
        except Exception:
            await self._fail(
                source,
                "parser_internal_error",
                "Document processing failed unexpectedly.",
            )
        return cast(UUID, source.source_id)

    async def _fail(self, source: Any, code: str, message: str) -> None:
        if self.repository is None:
            raise RuntimeError("Durable repository is required.")
        await _resolve(
            self.repository.fail_job(
                source.tenant_id,
                source.knowledge_base_id,
                source.source_id,
                error_code=code,
                error_message=message,
            )
        )

    async def ingest_source(
        self, source: KnowledgeBaseSource, content_raw: bytes | str
    ) -> list[KnowledgeBaseChunk]:
        """Parse bounded bytes through the compatibility entry point."""
        if isinstance(content_raw, str):
            if source.source_type != "pdf_upload":
                raise TypeError(
                    "Pre-extracted text is supported only for legacy PDF input."
                )
            return chunk_pdf_text(
                content_raw,
                tenant_id=source.tenant_id,
                config=self.config,
            )
        name = PurePath(source.source_uri).name
        media_type = source.source_type
        if "/" not in media_type:
            media_type = {
                "pdf_upload": "application/pdf",
                "faq_list": "application/json",
                "txt": "text/plain",
            }.get(media_type, media_type)
        validated = validate_upload(name, media_type, content_raw)
        document = await asyncio.wait_for(
            asyncio.to_thread(parse_document, validated, content_raw),
            timeout=self.parser_timeout_seconds,
        )
        return chunk_structured_document(
            document,
            tenant_id=source.tenant_id,
            source_id=source.source_id,
            config=self.config,
        )


async def _resolve(value: Any) -> Any:
    return await value if hasattr(value, "__await__") else value
