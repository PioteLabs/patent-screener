"""Persistent history of past screenings (SQLite), so results survive a server restart."""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from models import IdeaBreakdown, PatentReportEntry

DB_PATH = Path("patent_screener_history.sqlite")

# Rolling windows (seconds) for the homepage spend breakdown.
SPEND_WINDOWS: dict[str, float] = {
    "past_24_hours": 24 * 3600,
    "past_7_days": 7 * 24 * 3600,
    "past_month": 30 * 24 * 3600,
    "past_year": 365 * 24 * 3600,
}


def _connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
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
    db_path: Path = DB_PATH,
) -> None:
    conn = _connect(db_path)
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


def list_runs(limit: int = 50, db_path: Path = DB_PATH) -> list[dict]:
    conn = _connect(db_path)
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


def get_run(run_id: str, db_path: Path = DB_PATH) -> dict | None:
    conn = _connect(db_path)
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


def _run_has_conflict(entries: list[dict]) -> bool:
    """A run has a conflict if any compared claim fully reads on the idea."""
    return any(claim.get("reads_on_idea") for entry in entries for claim in entry.get("claims", []))


def dashboard_stats(db_path: Path = DB_PATH) -> dict:
    conn = _connect(db_path)
    rows = conn.execute("SELECT created_at, entries_json, usage_json FROM runs").fetchall()
    conn.close()

    now = time.time()
    cost_by_window = {key: 0.0 for key in SPEND_WINDOWS}
    cost_all_time = 0.0
    total_patents_screened = 0
    conflict_free_runs = 0

    for created_at, entries_json, usage_json in rows:
        cost = json.loads(usage_json).get("estimated_cost_usd", 0.0)
        cost_all_time += cost
        age = now - created_at
        for window, seconds in SPEND_WINDOWS.items():
            if age <= seconds:
                cost_by_window[window] += cost

        entries = json.loads(entries_json)
        total_patents_screened += len(entries)
        if not _run_has_conflict(entries):
            conflict_free_runs += 1

    total_runs = len(rows)
    return {
        "total_runs": total_runs,
        "total_patents_screened": total_patents_screened,
        "conflict_free_runs": conflict_free_runs,
        "runs_with_conflicts": total_runs - conflict_free_runs,
        "cost_all_time": round(cost_all_time, 4),
        "cost_past_year": round(cost_by_window["past_year"], 4),
        "cost_past_month": round(cost_by_window["past_month"], 4),
        "cost_past_7_days": round(cost_by_window["past_7_days"], 4),
        "cost_past_24_hours": round(cost_by_window["past_24_hours"], 4),
    }
