"""
Upstox API Module for Indian financial market data
Supports NSE, BSE, MCX, NFO, CDS exchanges
"""
from .client import UpstoxClient

__all__ = ["UpstoxClient"]
