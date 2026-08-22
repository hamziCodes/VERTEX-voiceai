"""Knowledge Base Data Models — Chunks, Sources & Chunking Configurations."""

from __future__ import annotations

from dataclasses import dataclass, field
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
