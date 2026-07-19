"""Optional LLM narrative summaries (Phase 10).

Turns the deterministic forecast / resource / roster outputs into a plain-language
summary for the dashboard's "AI Recommendation Explanation" panel.

Safety design:
- **Grounded:** the model may ONLY rephrase the structured numbers we pass it. It
  must not invent figures or give clinical advice.
- **Optional + graceful fallback:** if `GROQ_API_KEY` is unset or the call fails
  (e.g. offline — a real rural constraint), it returns a rule-based summary. The
  system never depends on the LLM.
"""
from __future__ import annotations

import httpx

from backend.config import settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = (
    "You are an assistant for a rural hospital operations dashboard. Write a short "
    "(3-5 sentence) plain-language briefing for a hospital administrator based ONLY "
    "on the JSON data provided. Do NOT invent numbers, do NOT give medical or "
    "clinical advice, and do NOT recommend anything not implied by the data. Focus "
    "on the demand outlook, the risk level, and which resources are short. Be calm "
    "and factual."
)


def _rule_based(ctx: dict) -> str:
    parts = [
        f"Forecast for {ctx.get('period', 'the period')}: about {ctx.get('avg_total', 'N/A')} "
        f"patients/day on average (peak {ctx.get('peak_total', 'N/A')}).",
        f"Overall capacity risk is {ctx.get('overall_risk', 'Unknown')}.",
    ]
    overload = ctx.get("overload_days") or []
    if overload:
        parts.append(f"Higher-strain days: {', '.join(overload)}.")
    shortages = ctx.get("top_shortages") or []
    if shortages:
        parts.append("Most frequent shortages: " + ", ".join(shortages) + ".")
    else:
        parts.append("No recurring resource shortages are projected.")
    return " ".join(parts)


def summarize(context: dict) -> dict:
    """Return {summary, source, [model], [error]}. Never raises."""
    if not settings.groq_api_key:
        return {"summary": _rule_based(context), "source": "rule-based"}
    try:
        import json
        resp = httpx.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            json={
                "model": settings.groq_model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(context)},
                ],
                "temperature": 0.3,
                "max_tokens": 300,
            },
            timeout=20,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"].strip()
        return {"summary": text, "source": "llm", "model": settings.groq_model}
    except Exception as e:  # noqa: BLE001  (any failure -> safe fallback)
        return {"summary": _rule_based(context), "source": "rule-based", "error": str(e)[:200]}
