"""Knowledge Base Data Models — Chunks, Sources & Chunking Configurations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


@dataclass
class ChunkConfig:
    """Configuration bounds for document chunking."""

    chunk_size_tokens: int = 400  # Default 400 tokens
    chunk_overlap_tokens: int = 64  # Default 64 tokens overlap


@dataclass
class KnowledgeBaseSource:
    """Document source metadata."""

    tenant_id: UUID
    source_type: str  # pdf_upload / faq_list / web_scrape / manual_entry
    source_uri: str
    source_id: UUID = field(default_factory=uuid4)
    refresh_interval_hours: int = 24


@dataclass
class KnowledgeBaseChunk:
    """Single vector chunk stored in pgvector table."""

    tenant_id: UUID
    text: str
    chunk_id: UUID = field(default_factory=uuid4)
    source_document_id: UUID = field(default_factory=uuid4)
    embedding: list[float] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class KnowledgeBaseStatus(StrEnum):
    DRAFT = "draft"
    PROCESSING = "processing"
    READY = "ready"
    ACTIVE = "active"
    FAILED = "failed"
    DELETING = "deleting"


class KnowledgeSourceStatus(StrEnum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    READY = "ready"
    FAILED = "failed"
    DELETING = "deleting"


class KnowledgeJobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class KnowledgeBaseRecord:
    tenant_id: UUID
    name: str
    knowledge_base_id: UUID = field(default_factory=uuid4)
    status: KnowledgeBaseStatus = KnowledgeBaseStatus.DRAFT
    active_revision: int = 0
    source_count: int = 0
    ready_source_count: int = 0
    total_chunks: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class KnowledgeSourceRecord:
    tenant_id: UUID
    knowledge_base_id: UUID
    source_type: str
    display_name: str
    media_type: str
    byte_count: int
    checksum_sha256: str
    object_reference: str
    source_id: UUID = field(default_factory=uuid4)
    revision: int = 1
    status: KnowledgeSourceStatus = KnowledgeSourceStatus.QUEUED
    chunk_count: int = 0
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class KnowledgeIngestionJob:
    tenant_id: UUID
    knowledge_base_id: UUID
    source_id: UUID
    idempotency_key: str
    job_id: UUID = field(default_factory=uuid4)
    state: KnowledgeJobState = KnowledgeJobState.QUEUED
    attempt: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class AgentKnowledgeBinding:
    tenant_id: UUID
    agent_id: UUID
    agent_config_version: int
    knowledge_base_id: UUID
    knowledge_revision: int
    binding_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
