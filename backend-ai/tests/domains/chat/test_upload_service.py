"""Unit tests for chat upload service behavior."""

import asyncio
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from src.domains.chat.upload_service import ChatUploadService


class _DummyDB:
    def __init__(self):
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1

    def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()

    def rollback(self):
        self.rollbacks += 1


class _DummyUploadFile:
    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self._content = content

    async def read(self) -> bytes:
        return self._content


class _FailingDocumentProcessor:
    def process(self, file_path: str, user_id: str, upload_id: str, file_type: str):
        raise RuntimeError("indexing failed")


def _run(coro):
    return asyncio.run(coro)


def test_upload_rejects_invalid_file_type():
    service = ChatUploadService(_DummyDB())
    file = _DummyUploadFile("notes.exe", b"abc")

    with pytest.raises(HTTPException) as exc:
        _run(
            service.upload_document(
                file=file,
                user_id=str(uuid.uuid4()),
                session_id=None,
            )
        )

    assert exc.value.status_code == 400
    assert "Unsupported file type" in exc.value.detail


def test_upload_rejects_invalid_user_uuid():
    service = ChatUploadService(_DummyDB())
    file = _DummyUploadFile("notes.txt", b"abc")

    with pytest.raises(HTTPException) as exc:
        _run(
            service.upload_document(
                file=file,
                user_id="not-a-uuid",
                session_id=None,
            )
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid user_id"


def test_upload_rejects_file_size_limit():
    service = ChatUploadService(_DummyDB())
    file = _DummyUploadFile("notes.txt", b"12345")

    with patch("src.domains.chat.upload_service.MAX_UPLOAD_SIZE_BYTES", 4):
        with pytest.raises(HTTPException) as exc:
            _run(
                service.upload_document(
                    file=file,
                    user_id=str(uuid.uuid4()),
                    session_id=None,
                )
            )

    assert exc.value.status_code == 400
    assert "File too large" in exc.value.detail


def test_upload_success_returns_metadata_and_indexes(tmp_path):
    db = _DummyDB()
    service = ChatUploadService(db)
    file = _DummyUploadFile("report.txt", b"hello world")
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()

    def _mark_indexed(self, upload, file_path, user_id):
        upload.status = "indexed"

    with patch("src.domains.chat.upload_service.UPLOAD_DIR", upload_dir), patch.object(
        ChatUploadService,
        "_process_document",
        new=_mark_indexed,
    ):
        result = _run(
            service.upload_document(
                file=file,
                user_id=str(uuid.uuid4()),
                session_id=None,
            )
        )

    assert result["filename"] == "report.txt"
    assert result["status"] == "indexed"
    assert result["file_size"] == len(b"hello world")
    assert len(result["hash"]) == 16

    saved_upload = db.added[0]
    assert Path(saved_upload.raw_uri).exists()
    assert Path(saved_upload.raw_uri).parent == upload_dir
    assert db.rollbacks == 0


def test_upload_indexing_failure_keeps_uploaded_status(tmp_path):
    db = _DummyDB()
    service = ChatUploadService(db)
    file = _DummyUploadFile("report.txt", b"hello world")
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()

    with patch("src.domains.chat.upload_service.UPLOAD_DIR", upload_dir), patch(
        "src.services.document_processor.DocumentProcessor",
        return_value=_FailingDocumentProcessor(),
    ):
        result = _run(
            service.upload_document(
                file=file,
                user_id=str(uuid.uuid4()),
                session_id=None,
            )
        )

    assert result["status"] == "uploaded"
    assert db.commits == 2
    assert db.rollbacks == 0
