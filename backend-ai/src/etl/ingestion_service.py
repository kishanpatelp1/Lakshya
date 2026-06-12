"""Service for ingesting and downloading documents from crawlers."""

import hashlib
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import UUID

import requests
from sqlalchemy.orm import Session

from src.db.models import Company, Filing
from src.config import get_settings

logger = logging.getLogger(__name__)

FILINGS_DIR = Path("uploads/filings")
FILINGS_DIR.mkdir(parents=True, exist_ok=True)

# Date formats seen across NSE/BSE/IR crawler outputs.
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M:%S",
    "%d-%b-%Y %H:%M:%S",
    "%d-%b-%Y",
    "%d-%m-%Y",
    "%d-%m-%Y %H:%M:%S",
    "%d %b %Y",
)


def _parse_filing_date(value: Optional[str]):
    """Best-effort parse of a crawler date string into a date; today() on failure."""
    from datetime import date as _date

    if not value or not isinstance(value, str):
        return datetime.utcnow().date()
    text = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    # ISO fallback (handles e.g. "2025-12-03T18:30:00")
    try:
        return datetime.fromisoformat(text.replace("Z", "")).date()
    except ValueError:
        return datetime.utcnow().date()


def _build_download_session(url: str) -> "requests.Session":
    """Return a requests session primed to download from exchange archives.

    NSE/BSE archives block generic bots — they require browser headers plus
    session cookies obtained by first visiting the main site.
    """
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    try:
        if "nseindia.com" in url:
            session.headers["Referer"] = (
                "https://www.nseindia.com/companies-listing/corporate-filings-announcements"
            )
            session.get("https://www.nseindia.com", timeout=10)
        elif "bseindia.com" in url:
            session.headers["Referer"] = "https://www.bseindia.com/"
            session.get("https://www.bseindia.com", timeout=10)
    except Exception:
        pass  # priming is best-effort; the download will still be attempted
    return session


class DocumentIngestionService:
    """Handles downloading and persisting filing documents."""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def ingest_filing(
        self,
        company_id: UUID,
        metadata: Dict[str, Any],
        download: bool = True,
    ) -> Optional[Filing]:
        """Persist a filing from crawler metadata, then optionally download the document.

        When ``download`` is False, only the metadata record is created (with its
        source_url). This keeps inline/synchronous callers fast — the UI links out
        to the source URL directly, so the PDF need not be fetched server-side.
        """
        source_url = metadata.get("attachment_url") or metadata.get("url") or ""

        # Phase 1: Deduplication check
        if source_url:
            existing = (
                self.db.query(Filing)
                .filter(
                    Filing.company_id == company_id,
                    Filing.source_url == source_url,
                )
                .first()
            )
            if existing:
                return existing
        else:
            # No URL — deduplicate by title to avoid exact duplicate metadata records
            title_candidate = metadata.get("subject", metadata.get("title", ""))
            if title_candidate:
                existing = (
                    self.db.query(Filing)
                    .filter(
                        Filing.company_id == company_id,
                        Filing.title == title_candidate,
                    )
                    .first()
                )
                if existing:
                    return existing

        # Phase 2: Always create the metadata record first
        filing_date = _parse_filing_date(metadata.get("date"))

        filing = Filing(
            company_id=company_id,
            filing_type=metadata.get("filing_type", "announcement"),
            title=metadata.get("subject", metadata.get("title", "Filing")),
            filing_date=filing_date,
            source_url=source_url or None,
            status="metadata_only",
            metadata_=metadata,
        )
        self.db.add(filing)
        self.db.commit()
        self.db.refresh(filing)
        logger.info("Saved filing metadata: %s for company %s", filing.title, company_id)

        # Phase 3: Attempt download (skipped when download=False; failure keeps status as metadata_only)
        if source_url and download:
            try:
                from requests.adapters import HTTPAdapter
                from urllib3.util.retry import Retry

                session = _build_download_session(source_url)
                retry_strategy = Retry(
                    total=2,
                    backoff_factor=1,
                    status_forcelist=[429, 500, 502, 503, 504],
                )
                adapter = HTTPAdapter(max_retries=retry_strategy)
                session.mount("https://", adapter)
                session.mount("http://", adapter)

                resp = session.get(source_url, timeout=30)
                if resp.status_code != 200 or not resp.content:
                    logger.warning("Download failed (%d) for filing %s", resp.status_code, filing.id)
                    filing.status = "download_failed"
                    self.db.commit()
                    return filing

                content = resp.content
                doc_hash = hashlib.sha256(content).hexdigest()

                # Dedup by hash
                existing_hash = (
                    self.db.query(Filing)
                    .filter(Filing.document_hash == doc_hash)
                    .first()
                )
                if existing_hash and existing_hash.id != filing.id:
                    logger.info("Duplicate content hash — deleting redundant metadata record %s", filing.id)
                    self.db.delete(filing)
                    self.db.commit()
                    return existing_hash

                # Save to filesystem
                filename = os.path.basename(source_url) or "document.pdf"
                if not filename.endswith((".pdf", ".pptx", ".ppt", ".txt", ".csv", ".xlsx")):
                    filename += ".pdf"
                safe_name = f"{doc_hash[:16]}_{filename}"
                file_path = FILINGS_DIR / safe_name
                with open(file_path, "wb") as f:
                    f.write(content)

                filing.raw_uri = str(file_path)
                filing.document_hash = doc_hash
                filing.status = "downloaded"
                self.db.commit()
                logger.info("Downloaded filing: %s", filing.title)

            except Exception as e:
                logger.warning("Download error for filing %s: %s", filing.id, e)
                try:
                    filing.status = "download_failed"
                    self.db.commit()
                except Exception:
                    pass

        return filing
