"""Gemini enrichment service for supplemental company metadata."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)


class GeminiEnrichmentService:
    """Fetches extra company context from Gemini when source APIs are sparse."""

    @staticmethod
    def _safe_json_object(value: str) -> Dict[str, Any]:
        """Parse model output into a JSON object safely."""
        text = value.strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text.replace("json", "", 1).strip()
        data = json.loads(text)
        if not isinstance(data, dict):
            return {}
        return data

    async def get_company_extra_info(
        self,
        company_name: str,
        ticker_nse: str | None,
        ticker_bse: str | None,
        known_fields: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Request supplemental company metadata from Gemini and return structured JSON."""
        settings = get_settings()
        if not settings.gemini_api_key:
            return self._fallback_stub(company_name)

        model = settings.gemini_model
        endpoint = f"{settings.gemini_base_url}/{model}:generateContent"

        known_payload = {
            "company_name": company_name,
            "ticker_nse": ticker_nse,
            "ticker_bse": ticker_bse,
            "known": known_fields,
        }
        prompt = (
            "You are a financial research assistant. Return ONLY valid JSON object with keys: "
            "business_model, key_products, primary_geographies, key_competitors, major_risks, "
            "management_notes, investment_highlights. "
            "Use short bullet-style strings inside arrays where applicable. "
            "If unknown, return null for that key. Do not hallucinate numbers. "
            f"Input: {json.dumps(known_payload, ensure_ascii=True)}"
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    endpoint,
                    params={"key": settings.gemini_api_key},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            candidates = data.get("candidates") or []
            if not candidates:
                return {}
            content = candidates[0].get("content") or {}
            parts = content.get("parts") or []
            if not parts:
                return {}

            text = str(parts[0].get("text") or "").strip()
            if not text:
                return {}
            return self._safe_json_object(text)
        except Exception as exc:
            logger.warning("Gemini enrichment failed for '%s': %s", company_name, exc)
            return self._fallback_stub(company_name)

    @staticmethod
    def _fallback_stub(company_name: str) -> Dict[str, Any]:
        """Return a minimal stub so frontend sections don't render blank."""
        return {
            "business_model": f"Enrichment data for {company_name} is temporarily unavailable. Click the refresh button to retry.",
            "key_products": None,
            "primary_geographies": ["India"],
            "key_competitors": None,
            "major_risks": ["Data temporarily unavailable — refresh to load risk analysis."],
            "management_notes": None,
            "investment_highlights": None,
            "_fallback": True,
        }

    def get_company_extra_info_sync(
        self,
        company_name: str,
        ticker_nse: str | None,
        ticker_bse: str | None,
        known_fields: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Synchronous Gemini enrichment variant for sync service flows."""
        settings = get_settings()
        if not settings.gemini_api_key:
            return self._fallback_stub(company_name)

        model = settings.gemini_model
        endpoint = f"{settings.gemini_base_url}/{model}:generateContent"

        known_payload = {
            "company_name": company_name,
            "ticker_nse": ticker_nse,
            "ticker_bse": ticker_bse,
            "known": known_fields,
        }
        prompt = (
            "You are a financial research assistant. Return ONLY valid JSON object with keys: "
            "business_model, key_products, primary_geographies, key_competitors, major_risks, "
            "management_notes, investment_highlights. "
            "Use short bullet-style strings inside arrays where applicable. "
            "If unknown, return null for that key. Do not hallucinate numbers. "
            f"Input: {json.dumps(known_payload, ensure_ascii=True)}"
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    endpoint,
                    params={"key": settings.gemini_api_key},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            candidates = data.get("candidates") or []
            if not candidates:
                return {}
            content = candidates[0].get("content") or {}
            parts = content.get("parts") or []
            if not parts:
                return {}

            text = str(parts[0].get("text") or "").strip()
            if not text:
                return {}
            return self._safe_json_object(text)
        except Exception as exc:
            logger.warning("Gemini enrichment failed for '%s': %s", company_name, exc)
            return self._fallback_stub(company_name)
