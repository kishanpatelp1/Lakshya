"""Database model for document chunks."""

from sqlalchemy import Column, String, Text, DateTime, Float, Integer
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.ext.declarative import declarative_base
import json

# Create chunks table
def create_chunks_table():
    """Create the chunks table in database."""
    pass