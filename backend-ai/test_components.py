#!/usr/bin/env python3

import sys
import os

# Add backend-ai to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend-ai'))

# Test the document processor
from src.etl.document_processor import DocumentProcessor
from src.etl.text_processor import TextCleaner, SemanticChunker
from src.etl.embedding_generator import EmbeddingGenerator

def test_components():
    print("Testing document processing components...")
    
    # Test document processor
    try:
        processor = DocumentProcessor()
        print("✓ Document processor created successfully")
    except Exception as e:
        print(f"✗ Error creating document processor: {e}")
        return
    
    # Test text processor
    try:
        cleaner = TextCleaner()
        print("✓ Text cleaner created successfully")
    except Exception as e:
        print(f"✗ Error creating text cleaner: {e}")
        return
    
    # Test semantic chunker
    try:
        chunker = SemanticChunker()
        print("✓ Semantic chunker created successfully")
    except Exception as e:
        print(f"✗ Error creating semantic chunker: {e}")
        return
    
    # Test with sample text
    sample_text = "This is a sample text for testing the document processing pipeline."
    try:
        cleaned = cleaner.clean_text(sample_text)
        print("✓ Text cleaning successful")
    except Exception as e:
        print(f"✗ Error cleaning text: {e}")
        return
    
    # Test chunking with small chunk size
    try:
        chunker = SemanticChunker(chunk_size=50, overlap=10)  # Small chunks for testing
        chunks = chunker.chunk_text(sample_text, "Test Company", "2023", "annual_report")
        print(f"✓ Chunking successful: {len(chunks)} chunks created")
    except Exception as e:
        print(f"✗ Error during chunking: {e}")
        return
    
    # Test embedding generator
    try:
        generator = EmbeddingGenerator("nomic-embed-text")
        print("✓ Embedding generator created successfully")
    except Exception as e:
        print(f"✗ Error creating embedding generator: {e}")
        return
    
    print("All components tested successfully!")

if __name__ == "__main__":
    test_components()()
    print("Text cleaner created successfully")
    
    # Test semantic chunker
    chunker = SemanticChunker()
    print("Semantic chunker created successfully")
    
    # Test with sample text
    sample_text = "This is a sample text for testing the document processing pipeline."
    cleaned = cleaner.clean_text(sample_text)
    print(f"Cleaned text: {cleaned}")
    
    # Test chunking with a smaller chunk size for faster execution
    chunker = SemanticChunker(chunk_size=100, overlap=20)  # Smaller chunks for testing
    chunks = chunker.chunk_text(cleaned, "Test Company", "2023", "annual_report")
    print(f"Created {len(chunks)} chunks")
    
    # Test embedding generator with Ollama
    generator = EmbeddingGenerator("nomic-embed-text")
    print("Embedding generator created successfully")
    
    # Test with actual embedding generation
    if chunks:
        # Extract just the texts for embedding
        texts = [chunk['text'] for chunk in chunks[:2]]  # Only process first 2 chunks for testing
        embeddings = generator.generate_embeddings(texts)
        print(f"Generated embeddings for {len(embeddings)} chunks")
    else:
        print("No chunks to embed")

if __name__ == "__main__":
    test_components()