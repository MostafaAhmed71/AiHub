#!/usr/bin/env python3
"""Thin wrapper — delegates to rag-service/scripts/seed_prompts.py."""

from __future__ import annotations

import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().parents[1] / "rag-service" / "scripts" / "seed_prompts.py"), run_name="__main__")
