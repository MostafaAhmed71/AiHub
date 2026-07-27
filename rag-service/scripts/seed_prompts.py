#!/usr/bin/env python3
"""Seed the Prompt Library with starter prompts across categories.

Run inside the rag-service container:
  PYTHONPATH=/app python scripts/seed_prompts.py

Or from host with DATABASE_URL set and rag-service on PYTHONPATH.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Ensure rag-service package is importable when run from repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.entities import Prompt

SEED_PROMPTS = [
    {
        "category": "School",
        "title": "Curriculum Q&A Tutor",
        "content": (
            "You are a tutor for {{subject}} grade {{grade}}. "
            "Answer the student question clearly in {{language}}. "
            "If the answer is not in the provided curriculum context, say you do not know."
        ),
        "variables": ["subject", "grade", "language"],
        "project_id": "school",
    },
    {
        "category": "School",
        "title": "Lesson Summary",
        "content": (
            "Summarize the following lesson notes for grade {{grade}} in {{language}}. "
            "Keep it under {{max_bullets}} bullet points and highlight key terms."
        ),
        "variables": ["grade", "language", "max_bullets"],
        "project_id": "school",
    },
    {
        "category": "Medical",
        "title": "Clinic Intake Summary",
        "content": (
            "Summarize the patient intake notes for clinic {{clinic_name}}. "
            "Extract chief complaint, history, and suggested next steps. "
            "Do not invent clinical facts. Language: {{language}}."
        ),
        "variables": ["clinic_name", "language"],
        "project_id": "clinicflow",
    },
    {
        "category": "Medical",
        "title": "Medication Reminder Message",
        "content": (
            "Draft a polite patient reminder about medication {{medication}} "
            "scheduled at {{time}}. Keep it under 2 sentences in {{language}}."
        ),
        "variables": ["medication", "time", "language"],
        "project_id": "clinicflow",
    },
    {
        "category": "ERP",
        "title": "Inventory Anomaly Explainer",
        "content": (
            "Explain the inventory anomaly for SKU {{sku}} at warehouse {{warehouse}}. "
            "Use only the provided ERP context. Suggest one verification step."
        ),
        "variables": ["sku", "warehouse"],
        "project_id": None,
    },
    {
        "category": "CRM",
        "title": "Lead Follow-up Email",
        "content": (
            "Write a short follow-up email to lead {{lead_name}} about product {{product}}. "
            "Tone: {{tone}}. Include a clear CTA."
        ),
        "variables": ["lead_name", "product", "tone"],
        "project_id": None,
    },
    {
        "category": "Marketing",
        "title": "Campaign Slogan Generator",
        "content": (
            "Generate 5 short slogans for {{product}} targeting {{audience}} in {{language}}. "
            "Avoid exaggerated medical/financial claims."
        ),
        "variables": ["product", "audience", "language"],
        "project_id": None,
    },
    {
        "category": "GasFlow",
        "title": "Delivery Status Reply",
        "content": (
            "Reply to a customer asking about cylinder delivery {{order_id}}. "
            "Status: {{status}}. ETA: {{eta}}. Be concise in {{language}}."
        ),
        "variables": ["order_id", "status", "eta", "language"],
        "project_id": "gasflow",
    },
]


async def main() -> int:
    async with AsyncSessionLocal() as session:
        inserted = 0
        for item in SEED_PROMPTS:
            existing = await session.execute(
                select(Prompt).where(
                    Prompt.category == item["category"],
                    Prompt.title == item["title"],
                    Prompt.project_id == item["project_id"],
                )
            )
            if existing.scalar_one_or_none():
                print(f"skip: {item['category']} / {item['title']}")
                continue
            session.add(Prompt(**item))
            inserted += 1
            print(f"seed: {item['category']} / {item['title']}")
        await session.commit()
    print(f"Done. Inserted {inserted} prompts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
