"""Business logic for chat document uploads and indexing."""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from src.db.models import UserUpload

logger = logging.getLogger(__name__)

MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".pptx", ".ppt", ".txt", ".csv", ".xlsx"}
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


class ChatUploadService:
    """Handles validation, persistence, and optional indexing of uploaded files."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _validate_filename(filename: Optional[str]) -> str:
        if not filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        return filename

    @staticmethod
    def _validate_extension(filename: str) -> str:
        extension = os.path.splitext(filename)[1].lower()
        if extension not in ALLOWED_EXTENSIONS:
            allowed_csv = ", ".join(sorted(ALLOWED_EXTENSIONS))
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {extension}. Allowed: {allowed_csv}",
            )
        return extension

    @staticmethod
    def _validate_size(content: bytes) -> None:
        if len(content) > MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(status_code=400, detail="File too large (max 50MB)")

    @staticmethod
    def _parse_uuid(value: str, field_name: str) -> UUID:
        try:
            return UUID(value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid {field_name}") from exc

    @staticmethod
    def _build_file_path(filename: str, content: bytes) -> tuple[str, Path]:
        doc_hash = hashlib.sha256(content).hexdigest()
        safe_name = f"{doc_hash[:16]}_{filename}"
        return doc_hash, UPLOAD_DIR / safe_name

    @staticmethod
    def _write_file(file_path: Path, content: bytes) -> None:
        with open(file_path, "wb") as output_file:
            output_file.write(content)

    def _create_upload_record(
        self,
        *,
        user_id: UUID,
        session_id: Optional[UUID],
        filename: str,
        extension: str,
        file_size_bytes: int,
        file_path: Path,
        document_hash: str,
    ) -> UserUpload:
        upload = UserUpload(
            user_id=user_id,
            session_id=session_id,
            filename=filename,
            file_type=extension.lstrip("."),
            file_size_bytes=file_size_bytes,
            raw_uri=str(file_path),
            document_hash=document_hash,
            status="uploaded",
        )
        self.db.add(upload)
        self.db.commit()
        self.db.refresh(upload)
        return upload

    def _process_document(self, upload: UserUpload, file_path: Path, user_id: UUID) -> None:
        try:
            from src.services.document_processor import DocumentProcessor

            processor = DocumentProcessor()
            chunk_count = processor.process(
                file_path=str(file_path),
                user_id=str(user_id),
                upload_id=str(upload.id),
                file_type=(upload.file_type or ""),
            )
            upload.status = "indexed"
            self.db.commit()
            logger.info("Indexed %d chunks for upload %s", chunk_count, upload.id)
        except Exception as proc_err:
            logger.warning("Document processing failed (upload saved): %s", proc_err)
            upload.status = "uploaded"
            self.db.commit()

    async def upload_document(
        self,
        *,
        file: UploadFile,
        user_id: str,
        session_id: Optional[str],
    ) -> dict[str, str | int]:
        filename = self._validate_filename(file.filename)
        extension = self._validate_extension(filename)

        content = await file.read()
        self._validate_size(content)

        parsed_user_id = self._parse_uuid(user_id, "user_id")
        parsed_session_id = (
            self._parse_uuid(session_id, "session_id") if session_id else None
        )

        doc_hash, file_path = self._build_file_path(filename, content)
        self._write_file(file_path, content)

        try:
            upload = self._create_upload_record(
                user_id=parsed_user_id,
                session_id=parsed_session_id,
                filename=filename,
                extension=extension,
                file_size_bytes=len(content),
                file_path=file_path,
                document_hash=doc_hash,
            )
            self._process_document(upload, file_path, parsed_user_id)

            return {
                "upload_id": str(upload.id),
                "filename": filename,
                "status": upload.status,
                "file_size": len(content),
                "hash": doc_hash[:16],
            }
        except HTTPException:
            self.db.rollback()
            raise
        except Exception as exc:
            self.db.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc
