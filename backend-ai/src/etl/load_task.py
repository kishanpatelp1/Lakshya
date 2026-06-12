"""Load task for inserting processed document chunks into Qdrant vector database."""

import logging
import uuid
from typing import List, Dict, Any

from src.config import get_settings

logger = logging.getLogger(__name__)

class ETLLoadTask:
    """Load task to store processed document chunks into vector database."""
    
    COLLECTION_NAME = "company_filings"
    
    def __init__(self):
        self.settings = get_settings()
        self._qdrant = None
        
    def _get_qdrant(self):
        if self._qdrant is None:
            from qdrant_client import QdrantClient
            self._qdrant = QdrantClient(
                url=self.settings.qdrant_url,
                api_key=self.settings.qdrant_api_key,
            )
        return self._qdrant
        
    def _ensure_collection(self, vector_size: int = 768) -> None:
        """Ensure the collection exists."""
        client = self._get_qdrant()
        from qdrant_client.models import Distance, VectorParams
        
        collections = [c.name for c in client.get_collections().collections]
        if self.COLLECTION_NAME not in collections:
            logger.info(f"Creating Qdrant collection: {self.COLLECTION_NAME}")
            client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE,
                ),
            )
            
    def load_chunks(self, chunks: List[Dict[str, Any]]) -> int:
        """Load embedded chunks into Qdrant."""
        if not chunks:
            return 0
            
        # Determine vector size from first chunk that has an embedding
        vector_size = 768 # Default for nomic-embed-text
        for chunk in chunks:
            if 'embedding' in chunk and chunk['embedding']:
                vector_size = len(chunk['embedding'])
                break
                
        self._ensure_collection(vector_size=vector_size)
        
        from qdrant_client.models import PointStruct
        points = []
        
        for chunk in chunks:
            if 'embedding' not in chunk or not chunk['embedding']:
                continue
                
            payload = {k: v for k, v in chunk.items() if k != 'embedding'}
            
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=chunk['embedding'],
                    payload=payload
                )
            )
            
        if not points:
            return 0
            
        client = self._get_qdrant()
        batch_size = 64
        
        try:
            for i in range(0, len(points), batch_size):
                client.upsert(
                    collection_name=self.COLLECTION_NAME,
                    points=points[i : i + batch_size],
                )
            logger.info(f"Loaded {len(points)} chunks into Qdrant collection {self.COLLECTION_NAME}")
            return len(points)
        except Exception as e:
            logger.error(f"Error loading chunks into Qdrant: {e}")
            return 0
