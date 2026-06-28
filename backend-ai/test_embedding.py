#!/usr/bin/env python3

import sys
import os

# Add backend-ai to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend-ai'))

# Test the embedding generator
from src.etl.embedding_generator import EmbeddingGenerator

def test_embedding_generator():
    # Test embedding generator with Ollama
    generator = EmbeddingGenerator("nomic-embed-text")
    print("Embedding generator created successfully")
    
    # Test with sample text
    sample_texts = [
        "This is a sample text for testing the document processing pipeline.",
        "This is another sample text for testing embeddings."
    ]
    
    embeddings = generator.generate_embeddings(sample_texts)
    print(f"Generated {len(embeddings)} embeddings")
    if embeddings:
        print(f"First embedding length: {len(embeddings[0])}")

if __name__ == "__main__":
    test_embedding_generator()