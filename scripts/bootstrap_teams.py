#!/usr/bin/env python3
"""Bootstrap LiteLLM Teams + Virtual Keys for AI Hub projects.

Creates one Team + Virtual Key per project, plus a dedicated rag-service team.
Requires LiteLLM to be running with a Master Key.

Usage:
  python scripts/bootstrap_teams.py
  LITELLM_BASE_URL=http://localhost:4000 LITELLM_MASTER_KEY=sk-... python scripts/bootstrap_teams.py
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import urllib.error
import urllib.request

BASE_URL = os.getenv("LITELLM_BASE_URL", "http://localhost:4000").rstrip("/")
MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "sk-aihub-master-change-me")

# Projects from PRD Phase 1
PROJECTS: list[dict[str, Any]] = [
    {
        "team_alias": "school",
        "max_budget": 50.0,
        "budget_duration": "30d",
        "rpm_limit": 60,
        "tpm_limit": 100000,
        "models": ["chat-default", "gemini/gemini-2.0-flash", "openai/gpt-4o-mini", "embedding-default"],
        "key_alias": "school-key",
    },
    {
        "team_alias": "clinicflow",
        "max_budget": 40.0,
        "budget_duration": "30d",
        "rpm_limit": 60,
        "tpm_limit": 80000,
        "models": ["chat-default", "gemini/gemini-2.0-flash", "openai/gpt-4o-mini"],
        "key_alias": "clinicflow-key",
    },
    {
        "team_alias": "gasflow",
        "max_budget": 30.0,
        "budget_duration": "30d",
        "rpm_limit": 40,
        "tpm_limit": 60000,
        "models": ["chat-default", "gemini/gemini-2.0-flash", "openai/gpt-4o-mini"],
        "key_alias": "gasflow-key",
    },
    {
        "team_alias": "rag-service",
        "max_budget": 100.0,
        "budget_duration": "30d",
        "rpm_limit": 120,
        "tpm_limit": 200000,
        "models": [
            "chat-default",
            "gemini/gemini-2.0-flash",
            "openai/gpt-4o-mini",
            "text-embedding-3-small",
            "text-embedding-004",
            "embedding-default",
        ],
        "key_alias": "rag-service-key",
        "key_env_hint": "RAG_SERVICE_VIRTUAL_KEY",
    },
]


def api(method: str, path: str, payload: dict | None = None) -> dict:
    url = f"{BASE_URL}{path}"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {MASTER_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} -> HTTP {exc.code}: {err}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cannot reach LiteLLM at {BASE_URL}: {exc}") from exc


def find_team(alias: str) -> dict | None:
    try:
        teams = api("GET", "/team/list")
    except RuntimeError:
        # Older/newer LiteLLM variants
        teams = api("GET", "/team/list?page=1&page_size=100")

    items = teams if isinstance(teams, list) else teams.get("teams") or teams.get("data") or []
    for team in items:
        if team.get("team_alias") == alias or team.get("team_id") == alias:
            return team
    return None


def ensure_team(project: dict[str, Any]) -> str:
    existing = find_team(project["team_alias"])
    if existing:
        team_id = existing.get("team_id") or existing.get("team_alias")
        print(f"  team exists: {project['team_alias']} ({team_id})")
        return str(team_id)

    created = api(
        "POST",
        "/team/new",
        {
            "team_alias": project["team_alias"],
            "max_budget": project["max_budget"],
            "budget_duration": project["budget_duration"],
            "models": project["models"],
            "rpm_limit": project.get("rpm_limit"),
            "tpm_limit": project.get("tpm_limit"),
        },
    )
    team_id = created.get("team_id") or created.get("team_alias")
    print(f"  team created: {project['team_alias']} ({team_id})")
    return str(team_id)


def create_key(project: dict[str, Any], team_id: str) -> str:
    created = api(
        "POST",
        "/key/generate",
        {
            "key_alias": project["key_alias"],
            "team_id": team_id,
            "models": project["models"],
            "max_budget": project["max_budget"],
            "budget_duration": project["budget_duration"],
            "rpm_limit": project.get("rpm_limit"),
            "tpm_limit": project.get("tpm_limit"),
            "metadata": {"project": project["team_alias"], "hub": "aihub"},
        },
    )
    key = created.get("key") or created.get("api_key")
    if not key:
        raise RuntimeError(f"No key returned for {project['key_alias']}: {created}")
    return key


def main() -> int:
    print(f"Bootstrapping AI Hub teams against {BASE_URL}")
    results: list[dict[str, str]] = []

    for project in PROJECTS:
        print(f"\n[{project['team_alias']}]")
        try:
            team_id = ensure_team(project)
            key = create_key(project, team_id)
            hint = project.get("key_env_hint", f"{project['team_alias'].upper()}_VIRTUAL_KEY")
            results.append(
                {
                    "project": project["team_alias"],
                    "team_id": team_id,
                    "key_alias": project["key_alias"],
                    "virtual_key": key,
                    "env": hint,
                }
            )
            print(f"  virtual key: {key}")
            print(f"  set {hint}={key}")
        except Exception as exc:
            print(f"  ERROR: {exc}", file=sys.stderr)
            return 1

    out_path = os.getenv("BOOTSTRAP_OUTPUT", "bootstrap-keys.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
    print(f"\nWrote keys to {out_path} — keep this file secret.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
