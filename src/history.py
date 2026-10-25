"""Persistent history of past screenings (SQLite), so results survive a server restart."""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from models import IdeaBreakdown, PatentReportEntry

DB_PATH = Path("patent_screener_history.sqlite")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            created_at REAL,
            idea_json TEXT,
            entries_json TEXT,
            sources_searched_json TEXT,
            skipped_json TEXT,
            usage_json TEXT
        )
        """
    )
    return conn


def save_run(
    run_id: str,
    idea: IdeaBreakdown,
    entries: list[PatentReportEntry],
    sources_searched: dict[str, int],
    skipped: list[str],
    usage: dict,
) -> None:
    conn = _connect()
    conn.execute(
        """INSERT OR REPLACE INTO runs
           (id, created_at, idea_json, entries_json, sources_searched_json, skipped_json, usage_json)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id,
            time.time(),
            idea.model_dump_json(),
            json.dumps([e.model_dump(mode="json") for e in entries]),
            json.dumps(sources_searched),
            json.dumps(skipped),
            json.dumps(usage),
        ),
    )
    conn.commit()
    conn.close()


def list_runs(limit: int = 50) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT id, created_at, idea_json, entries_json, usage_json FROM runs ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    runs = []
    for run_id, created_at, idea_json, entries_json, usage_json in rows:
        idea = json.loads(idea_json)
        entries = json.loads(entries_json)
        usage = json.loads(usage_json)
        runs.append(
            {
                "id": run_id,
                "created_at_display": datetime.fromtimestamp(created_at).strftime("%Y-%m-%d %H:%M"),
                "summary": idea.get("summary", ""),
                "num_matches": len(entries),
                "cost": usage.get("estimated_cost_usd", 0.0),
            }
        )
    return runs


def get_run(run_id: str) -> dict | None:
    conn = _connect()
    row = conn.execute(
        """SELECT idea_json, entries_json, sources_searched_json, skipped_json, usage_json
           FROM runs WHERE id = ?""",
        (run_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    idea_json, entries_json, sources_searched_json, skipped_json, usage_json = row
    return {
        "idea": IdeaBreakdown.model_validate_json(idea_json),
        "entries": [PatentReportEntry.model_validate(e) for e in json.loads(entries_json)],
        "sources_searched": json.loads(sources_searched_json),
        "skipped": json.loads(skipped_json),
        "usage": json.loads(usage_json),
    }
