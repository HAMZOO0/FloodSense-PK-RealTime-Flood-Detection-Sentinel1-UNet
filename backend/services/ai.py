"""FloodAI (Gemini/Groq) singleton — risk scoring + strategic insights + chat LLM."""

import logging
import threading

logger = logging.getLogger("floodsense.ai")

_lock = threading.Lock()
_flood_ai = None


def get_flood_ai():
    """Lazily build the shared FloodAI client (Gemini primary, Groq secondary)."""
    global _flood_ai
    if _flood_ai is None:
        with _lock:
            if _flood_ai is None:
                from engine.ai_alerts import FloodAI

                _flood_ai = FloodAI()
    return _flood_ai


def generate_insights(analysis: dict, river_stations: list[dict]) -> dict:
    """Grounded strategic insights for a completed analysis document.

    Falls back to FloodAI's simulated report when no LLM key is configured,
    so this endpoint never hard-fails on missing API keys.
    """
    ai = get_flood_ai()
    district_data = [
        {
            "district": analysis["district"],
            "flood_pct_current": analysis["flood_pct_current"],
            "flood_pct_2010": analysis["flood_pct_2010"],
            "river_status": (analysis.get("river") or {}).get("status", "UNKNOWN"),
        }
    ]
    insights = ai.generate_insights(district_data, river_stations)
    return {
        "district": analysis["district"],
        "insights": insights,
        "llm_used": bool(ai.enabled),
        "based_on_analysis_id": analysis.get("id"),
    }


def llm_fn(prompt: str) -> str | None:
    """Single-prompt completion for RAG chat; None when no LLM is reachable."""
    ai = get_flood_ai()

    if getattr(ai, "gemini_enabled", False):
        try:
            response = ai.gemini_client.models.generate_content(
                model=ai.gemini_model_name, contents=prompt
            )
            return response.text
        except Exception as e:
            logger.warning("Gemini chat call failed: %s", e)

    if getattr(ai, "groq_enabled", False):
        try:
            resp = ai.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content
        except Exception as e:
            logger.warning("Groq chat call failed: %s", e)

    return None
