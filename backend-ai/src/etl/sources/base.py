"""Common interface for document sources.

Each source returns a list of metadata dicts shaped for
``DocumentIngestionService.ingest_filing`` — i.e. carrying at least
``attachment_url`` plus ``title`` / ``filing_type`` / ``date`` — so the
existing ingestion + ETL pipeline can consume them unchanged.
"""

from abc import ABC, abstractmethod
from typing import Any


class DocumentSource(ABC):
    """A pluggable place to discover a company's documents."""

    name: str = "source"

    @abstractmethod
    def fetch(self, company: Any) -> list[dict[str, Any]]:
        """Return document metadata dicts for a ``Company`` row.

        Keys used downstream: ``attachment_url`` (required), ``title``,
        ``filing_type``, ``date``, ``doc_type``.
        """
        raise NotImplementedError
