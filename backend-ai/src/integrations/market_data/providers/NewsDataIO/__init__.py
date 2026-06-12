"""
NewsData.io API Integration
Real-time and historical news from 92,000+ sources across 206 countries.
Includes dedicated Market, Crypto, Archive, and Sources endpoints.
"""

from .client import NewsDataIOClient

__version__ = "1.0.0"

__all__ = ["NewsDataIOClient"]
