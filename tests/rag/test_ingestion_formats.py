from __future__ import annotations

import io
import json
import time
from uuid import uuid4

import pytest

from core.rag.ingestion.parsers.base import IngestionParseError
from core.rag.ingestion.parsers.registry import parse_document
from core.rag.ingestion.validation import validate_upload
from core.rag.ingestion.worker import IngestionWorker
from core.storage.knowledge_objects import LocalKnowledgeObjectStore


def _docx_bytes() -> bytes:
    from docx import Document

    output = io.BytesIO()
    document = Document()
    document.add_heading("Returns", level=1)
    document.add_paragraph("Items may be returned within fourteen days.")
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Region"
    table.rows[0].cells[1].text = "Window"
    document.save(output)
    return output.getvalue()


def _xlsx_bytes() -> bytes:
    from openpyxl import Workbook

    output = io.BytesIO()
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Catalog"
    sheet.append(["Product", "Price"])
    sheet.append(["Tea", 250])
    sheet["C2"] = "=1+1"
    workbook.save(output)
    return output.getvalue()


@pytest.mark.parametrize(
    ("name", "media_type", "content", "needle"),
    [
        ("guide.txt", "text/plain", b"Welcome to support", "Welcome"),
        ("guide.md", "text/markdown", b"# Setup\nInstall safely", "Setup"),
        ("rates.csv", "text/csv", b"country,rate\nPK,10\n", "country"),
    ],
)
def test_text_formats_preserve_traceable_locations(
    name: str, media_type: str, content: bytes, needle: str
) -> None:
    parsed = parse_document(validate_upload(name, media_type, content), content)
    assert needle in "\n".join(section.text for section in parsed.sections)
    assert all(section.citation for section in parsed.sections)


def test_docx_and_xlsx_extract_structure_without_formula_execution() -> None:
    docx = _docx_bytes()
    parsed_docx = parse_document(
        validate_upload(
            "returns.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            docx,
        ),
        docx,
    )
    assert "fourteen days" in "\n".join(s.text for s in parsed_docx.sections)

    xlsx = _xlsx_bytes()
    parsed_xlsx = parse_document(
        validate_upload(
            "catalog.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            xlsx,
        ),
        xlsx,
    )
    text = "\n".join(s.text for s in parsed_xlsx.sections)
    assert "Tea" in text
    assert "=1+1" not in text


def test_malformed_docx_xml_returns_typed_failure() -> None:
    import zipfile

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as bundle:
        bundle.writestr("[Content_Types].xml", "<Types>")
        bundle.writestr("word/document.xml", "<broken")
    content = output.getvalue()
    validated = validate_upload(
        "broken.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        content,
    )
    with pytest.raises(IngestionParseError, match="docx_malformed"):
        parse_document(validated, content)


def test_encrypted_and_image_only_pdfs_fail_with_typed_errors() -> None:
    from pypdf import PdfWriter

    image_only = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(image_only)
    raw = image_only.getvalue()
    with pytest.raises(IngestionParseError, match="pdf_no_extractable_text"):
        parse_document(validate_upload("scan.pdf", "application/pdf", raw), raw)

    encrypted = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("password")
    writer.write(encrypted)
    raw = encrypted.getvalue()
    with pytest.raises(IngestionParseError, match="pdf_encrypted"):
        parse_document(validate_upload("private.pdf", "application/pdf", raw), raw)


def test_faq_items_are_bounded_and_traceable() -> None:
    content = json.dumps(
        [{"question": "When are you open?", "answer": "Every weekday."}]
    ).encode()
    parsed = parse_document(
        validate_upload("faq.json", "application/json", content), content
    )
    assert parsed.sections[0].citation == {"faq_item": 1}


@pytest.mark.asyncio
async def test_worker_claims_processes_and_survives_restart(tmp_path) -> None:
    from core.db.repos.knowledge_repo import InMemoryKnowledgeRepository

    repository = InMemoryKnowledgeRepository()
    tenant_id = uuid4()
    base = repository.create_knowledge_base(tenant_id, "Policies")
    store = LocalKnowledgeObjectStore(tmp_path)
    content = b"Returns are accepted for fourteen days."
    validated = validate_upload("returns.txt", "text/plain", content)
    object_reference = await store.put(tenant_id, content, suffix=".txt")
    source = repository.create_source(
        tenant_id,
        base.knowledge_base_id,
        source_type=validated.source_type,
        display_name=validated.display_name,
        media_type=validated.media_type,
        byte_count=validated.byte_count,
        checksum_sha256=validated.checksum_sha256,
        object_reference=object_reference,
    )

    first_worker = IngestionWorker(repository, store, worker_id="worker-a")
    assert await first_worker.process_next() == source.source_id
    restarted_worker = IngestionWorker(repository, store, worker_id="worker-b")
    assert await restarted_worker.process_next() is None
    completed = repository.get_source(
        tenant_id, base.knowledge_base_id, source.source_id
    )
    assert completed.status.value == "embedding"
    assert completed.chunk_count == 1


@pytest.mark.asyncio
async def test_worker_timeout_is_retryable(monkeypatch, tmp_path) -> None:
    import core.rag.ingestion.worker as worker_module
    from core.db.repos.knowledge_repo import InMemoryKnowledgeRepository

    repository = InMemoryKnowledgeRepository()
    tenant_id = uuid4()
    base = repository.create_knowledge_base(tenant_id, "Slow")
    store = LocalKnowledgeObjectStore(tmp_path)
    content = b"eventually parsed"
    validated = validate_upload("slow.txt", "text/plain", content)
    reference = await store.put(tenant_id, content, suffix=".txt")
    source = repository.create_source(
        tenant_id,
        base.knowledge_base_id,
        source_type="txt",
        display_name="slow.txt",
        media_type="text/plain",
        byte_count=len(content),
        checksum_sha256=validated.checksum_sha256,
        object_reference=reference,
    )
    original = worker_module.parse_document

    def slow_parser(*args):
        time.sleep(0.05)
        return original(*args)

    monkeypatch.setattr(worker_module, "parse_document", slow_parser)
    worker = IngestionWorker(repository, store, parser_timeout_seconds=0.001)
    assert await worker.process_next() == source.source_id
    failed = repository.get_source(tenant_id, base.knowledge_base_id, source.source_id)
    assert failed.error_code == "parser_timeout"
    retried = repository.retry_source(
        tenant_id, base.knowledge_base_id, source.source_id
    )
    assert retried.state.value == "queued"
    assert retried.attempt == 2
