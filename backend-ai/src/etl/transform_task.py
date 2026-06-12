"""Main ETL Transform task implementation."""

import logging
from typing import List, Dict, Any
from pathlib import Path

from src.etl.document_processor import DocumentProcessor
from src.etl.text_processor import TextCleaner, SemanticChunker
from src.etl.embedding_generator import EmbeddingGenerator
from src.etl.enricher import FilingEnricher

logger = logging.getLogger(__name__)

class ETLTransformTask:
    """Main ETL Transform task that processes filings through the pipeline."""
    
    def __init__(self):
        self.document_processor = DocumentProcessor()
        self.text_cleaner = TextCleaner()
        self.chunker = SemanticChunker()
        self.embedding_generator = EmbeddingGenerator("nomic-embed-text")
        self.enricher = FilingEnricher()
        
    def process_filing(self, file_path: str, **metadata) -> List[Dict[str, Any]]:
        """Process a filing through the entire pipeline."""
        # Process document
        processed_doc = self.document_processor.process_document(file_path)
        if not processed_doc:
            return []
            
        # Generate timeline summary, metrics, and red flags via LLM
        enrichment_data = self.enricher.enrich_filing(processed_doc['text'], metadata)
        
        # Clean text
        cleaned_text = self.text_cleaner.clean_text(processed_doc['text'])
        normalized_text = self.text_cleaner.normalize_text(cleaned_text)
        
        # Chunk text
        chunks = self.chunker.chunk_text(
            normalized_text,
            **metadata
        )

        # Contextual retrieval: prepend a situating header to every chunk before
        # embedding, so vectors carry "which company / which document / which
        # section" context — measurably better retrieval than bare chunk text.
        header_bits = [
            metadata.get("company_name") or "",
            f"{metadata.get('document_type') or ''} {metadata.get('filing_date') or ''}".strip(),
        ]
        base_header = " — ".join(b for b in header_bits if b)
        if base_header:
            for ch in chunks:
                section = ch.get("section") or ""
                header = f"[{base_header}{' — ' + section if section else ''}] "
                ch["text"] = header + (ch.get("text") or "")

        # Generate embeddings. Degrade gracefully if the embedder (Ollama) is
        # unavailable — the enrichment/insights must still be persisted.
        try:
            embedded_chunks = self.embedding_generator.generate_document_embeddings(chunks)
        except Exception as e:
            logger.warning("Embedding generation failed (%s); continuing without vectors", e)
            embedded_chunks = []

        return {
            "chunks": embedded_chunks,
            "enrichment": enrichment_data
        }

# Example usage
if __name__ == "__main__":
    # This would be used in the actual ETL pipeline
    pass