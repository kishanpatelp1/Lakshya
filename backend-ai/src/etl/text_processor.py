"""Text processing utilities for cleaning and chunking financial documents."""

import re
import logging
from typing import List, Dict, Any
import hashlib

logger = logging.getLogger(__name__)

class TextCleaner:
    """Clean and preprocess text for financial document processing."""
    
    def __init__(self):
        # Common patterns for financial documents
        self.headers_footers_patterns = [
            r'Page \d+ of \d+',
            r'\b(Page\s+\d+(?:\s+of\s+\d+)?)\b',
            r'\b(\d{1,2}/\d{1,2}/\d{4})\b',  # Dates
            r'\b(\d{1,2}-\d{1,2}-\d{4})\b',   # Alternative date format
        ]
        
    def clean_text(self, text: str) -> str:
        """Clean text by removing headers, footers, and noise."""
        if not text:
            return ""
            
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove common headers/footers
        for pattern in self.headers_footers_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
            
        # Remove extra spaces
        text = re.sub(r'\s+', ' ', text).strip()
        return text
        
    def normalize_text(self, text: str) -> str:
        """Normalize text formatting and currency."""
        if not text:
            return ""
            
        # Normalize currency formats
        text = re.sub(r'Rs\.?\s*', '₹', text)  # Indian Rupee symbol
        text = re.sub(r'\$\s*', '$', text)      # USD symbol
        text = re.sub(r'USD\s*', 'USD ', text)  # USD text
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text

class SemanticChunker:
    """Chunk text into semantic sections for better retrieval."""
    
    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.section_patterns = [
            r'(Management\s+Discussion\s+and\s+Analysis)',
            r'(Risk\s+Factors)',
            r'(Financial\s+Statements?)',
            r'(Directors\'\s+Report)',
            r'(Auditors?\'\s+Report)',
            r'(Corporate\s+Governance)',
            r'(Business\s+Overview)',
            r'(Operations\s+Review)',
            r'(Financial\s+Performance)',
            r'(Key\s+Management\s+Personnel)',
            r'(Related\s+Party\s+Transactions?)',
            r'(Internal\s+Controls?)',
            r'(Compliance\s+with\s+Listing\s+Requirements?)'
        ]
        
    def chunk_text(self, text: str, **metadata) -> List[Dict[str, Any]]:
        """Chunk text into semantic sections."""
        if not text:
            return []
            
        chunks = []
        current_position = 0
        text_length = len(text)
        
        # First try to identify major sections
        section_matches = []
        for pattern in self.section_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                section_matches.append((match.start(), match.end(), match.group()))
                
        # Sort by position
        section_matches.sort(key=lambda x: x[0])
        
        # If we found sections, chunk by sections
        if section_matches:
            for i, (start, end, section_name) in enumerate(section_matches):
                # Get text from previous section to this section
                if i == 0:
                    section_text = text[:start]
                    if section_text.strip():
                        chunks.extend(self._create_chunks(
                            section_text, 
                            f"introduction_{section_name.lower().replace(' ', '_')}",
                            **metadata
                        ))
                
                # Get text for this section
                next_start = section_matches[i+1][0] if i+1 < len(section_matches) else len(text)
                section_text = text[start:next_start]
                if section_text.strip():
                    chunks.extend(self._create_chunks(
                        section_text, 
                        section_name.lower().replace(' ', '_').replace('\'', ''),
                        **metadata
                    ))
        else:
            # No sections found, chunk the whole text
            chunks.extend(self._create_chunks(text, "general", **metadata))
            
        return chunks
        
    def _create_chunks(self, text: str, section: str = "general", **metadata) -> List[Dict[str, Any]]:
        """Create individual chunks from text."""
        if not text.strip():
            return []
            
        chunks = []
        words = text.split()
        
        if not words:
            return []
            
        # Create chunks with overlap
        start = 0
        while start < len(words):
            end = min(start + self.chunk_size, len(words))
            chunk_words = words[start:end]
            chunk_text = " ".join(chunk_words)
            
            # Create chunk ID
            chunk_id = hashlib.md5(chunk_text.encode()).hexdigest()[:16]
            
            chunk_data = {
                "chunk_id": chunk_id,
                "text": chunk_text,
                "section": section,
                "start_position": start,
                "end_position": end
            }
            chunk_data.update(metadata)
            chunks.append(chunk_data)
            
            if end == len(words):
                break
                
            # Move start position with overlap
            start = end - self.overlap
                
        return chunks