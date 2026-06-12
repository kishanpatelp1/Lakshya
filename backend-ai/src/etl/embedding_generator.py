"""Embedding generation for document chunks using Ollama."""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class EmbeddingGenerator:
    """Generate embeddings for document chunks using Ollama."""
    
    def __init__(self, model_name: str = "nomic-embed-text"):
        self.model_name = model_name
        logger.info(f"Using embedding model: {self.model_name}")
            
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for document chunks."""
        try:
            from src.llm import get_embeddings
            embeddings_model = get_embeddings()
            return embeddings_model.embed_documents(texts)
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return []
            
    def generate_document_embeddings(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate embeddings for document chunks."""
        try:
            # Extract texts for embedding
            texts = [chunk['text'] for chunk in chunks]
            
            # Generate embeddings
            embeddings = self.generate_embeddings(texts)
            
            # Add embeddings to chunks
            for i, chunk in enumerate(chunks):
                if i < len(embeddings):
                    chunk['embedding'] = embeddings[i]
                
            return chunks
        except Exception as e:
            logger.error(f"Error generating document embeddings: {e}")
            # Return chunks without embeddings
            return chunks