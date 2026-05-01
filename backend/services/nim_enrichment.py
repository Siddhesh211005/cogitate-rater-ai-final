"""
backend/services/nim_enrichment.py

NVIDIA NIM LLM Enrichment Service
===================================
Called once at schema upload time to enrich raw field names into
human-readable labels and descriptions. Uses the NVIDIA NIM API
(OpenAI-compatible endpoint) with a free developer account.

Only used during the Schema Engine upload path. Excel Engine raters
get their labels from the _Schema sheet directly.

Rate limit: ~40 req/min on free tier. We batch all fields into a
single prompt to stay well within limits.

Config (environment variables):
  NIM_API_KEY   — NVIDIA NIM API key
  NIM_BASE_URL  — defaults to https://integrate.api.nvidia.com/v1
  NIM_MODEL     — defaults to meta/llama-3.1-8b-instruct
"""

from __future__ import annotations

import os
import json
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

NIM_BASE_URL = os.getenv("NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")
NIM_API_KEY = os.getenv("NIM_API_KEY", "")
NIM_MODEL = os.getenv("NIM_MODEL", "meta/llama-3.1-8b-instruct")
NIM_TIMEOUT = 30  # seconds


# ---------------------------------------------------------------------------
# Core enrichment call
# ---------------------------------------------------------------------------

async def enrich_fields(fields: list[dict]) -> list[dict]:
    """
    Given a list of raw field dicts (from schema_parser), return the same
    list with `label` and `description` populated by the LLM.

    Input field shape (what schema_parser produces):
        {
            "field": "state_of_risk",
            "cell": "B11",
            "type": "dropdown",
            "label": "state_of_risk",   ← raw, needs enrichment
            "description": "",          ← empty, needs enrichment
            "group": "Rating Inputs",
            "options": [...],
            "default": "CO"
        }

    If NIM_API_KEY is not set or the call fails, fields are returned
    unchanged — enrichment is best-effort, never blocking.
    """
    if not NIM_API_KEY:
        logger.warning("NIM_API_KEY not set — skipping enrichment")
        return fields

    if not fields:
        return fields

    try:
        enriched = await _call_nim(fields)
        return enriched
    except Exception:
        logger.exception("NIM enrichment failed — returning raw fields")
        return fields


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _build_prompt(fields: list[dict]) -> str:
    field_lines = "\n".join(
        f"- field: {f['field']}, type: {f['type']}, group: {f.get('group', '')}"
        for f in fields
    )
    return f"""You are enriching fields for an insurance premium rating form.

Given these raw field names from a parsed Excel rater workbook, return a JSON array
where each object has:
  - "field": the original field name (unchanged)
  - "label": a clean, human-readable label (Title Case, no underscores, ≤6 words)
  - "description": a brief tooltip for an insurance underwriter (1 sentence, ≤20 words)

Fields to enrich:
{field_lines}

Respond ONLY with a valid JSON array. No markdown, no explanation, no preamble.
Example:
[
  {{"field": "state_of_risk", "label": "State of Risk", "description": "The US state where the insured risk is located."}}
]"""


async def _call_nim(fields: list[dict]) -> list[dict]:
    prompt = _build_prompt(fields)

    payload = {
        "model": NIM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024,
        "temperature": 0.2,
    }

    headers = {
        "Authorization": f"Bearer {NIM_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=NIM_TIMEOUT) as client:
        response = await client.post(
            f"{NIM_BASE_URL}/chat/completions",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()

    raw = response.json()["choices"][0]["message"]["content"].strip()

    # Strip markdown fences if model wraps output anyway
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    enriched_map: dict[str, dict] = {
        item["field"]: item for item in json.loads(raw)
    }

    # Merge enriched label/description back onto original field dicts
    result = []
    for f in fields:
        enriched = enriched_map.get(f["field"], {})
        result.append({
            **f,
            "label": enriched.get("label") or f.get("label") or f["field"],
            "description": enriched.get("description") or f.get("description") or "",
        })

    logger.info("NIM enrichment complete: %d fields enriched", len(result))
    return result


# ---------------------------------------------------------------------------
# Convenience wrapper for output fields (same logic, different prompt framing)
# ---------------------------------------------------------------------------

async def enrich_outputs(fields: list[dict]) -> list[dict]:
    """
    Same as enrich_fields but for output fields. Separated so the prompt
    can frame them correctly as calculated results, not user inputs.
    """
    if not NIM_API_KEY or not fields:
        return fields

    for f in fields:
        f["_is_output"] = True  # temp flag for prompt builder

    try:
        prompt = _build_output_prompt(fields)
        result = await _call_nim_raw(prompt, fields)
        return result
    except Exception:
        logger.exception("NIM output enrichment failed — returning raw fields")
        for f in fields:
            f.pop("_is_output", None)
        return fields


def _build_output_prompt(fields: list[dict]) -> str:
    field_lines = "\n".join(
        f"- field: {f['field']}, type: {f['type']}"
        for f in fields
    )
    return f"""You are labeling output fields for an insurance premium rating results dashboard.

Given these calculated output field names from an Excel rater workbook, return a JSON array
where each object has:
  - "field": the original field name (unchanged)
  - "label": a clean, human-readable label (Title Case, ≤6 words)
  - "description": what this output represents for an underwriter (1 sentence, ≤20 words)

Output fields:
{field_lines}

Respond ONLY with a valid JSON array. No markdown, no explanation.
Example:
[
  {{"field": "total_premium", "label": "Total Premium", "description": "The final calculated premium due for this policy."}}
]"""


async def _call_nim_raw(prompt: str, original_fields: list[dict]) -> list[dict]:
    """Internal: call NIM with a custom prompt, merge results back."""
    payload = {
        "model": NIM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 512,
        "temperature": 0.2,
    }
    headers = {
        "Authorization": f"Bearer {NIM_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=NIM_TIMEOUT) as client:
        response = await client.post(
            f"{NIM_BASE_URL}/chat/completions",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()

    raw = response.json()["choices"][0]["message"]["content"].strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    enriched_map = {item["field"]: item for item in json.loads(raw)}

    result = []
    for f in original_fields:
        f.pop("_is_output", None)
        enriched = enriched_map.get(f["field"], {})
        result.append({
            **f,
            "label": enriched.get("label") or f.get("label") or f["field"],
            "description": enriched.get("description") or f.get("description") or "",
        })
    return result