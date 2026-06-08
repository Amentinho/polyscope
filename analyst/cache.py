"""SQLite-backed cache for Claude analysis results."""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

CACHE_PATH = Path(__file__).parent.parent / "data" / "analysis_cache.db"
CACHE_PATH.parent.mkdir(exist_ok=True)

# How long to trust a cached result (hours). News-driven edges decay fast.
CACHE_TTL_HOURS = 4


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(CACHE_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            key TEXT PRIMARY KEY,
            result TEXT NOT NULL,
            cached_at TEXT NOT NULL
        )
    """)
    con.commit()
    return con


def _make_key(news_ids: list[str], condition_id: str) -> str:
    payload = condition_id + "|" + ",".join(sorted(news_ids))
    return hashlib.sha256(payload.encode()).hexdigest()


def get(news_ids: list[str], condition_id: str) -> dict | None:
    key = _make_key(news_ids, condition_id)
    con = _conn()
    row = con.execute("SELECT result, cached_at FROM cache WHERE key = ?", (key,)).fetchone()
    con.close()
    if not row:
        return None
    result, cached_at = row
    age_hours = (datetime.now(timezone.utc) - datetime.fromisoformat(cached_at)).total_seconds() / 3600
    if age_hours > CACHE_TTL_HOURS:
        return None
    return json.loads(result)


def put(news_ids: list[str], condition_id: str, result: dict):
    key = _make_key(news_ids, condition_id)
    con = _conn()
    con.execute(
        "INSERT OR REPLACE INTO cache (key, result, cached_at) VALUES (?, ?, ?)",
        (key, json.dumps(result), datetime.now(timezone.utc).isoformat()),
    )
    con.commit()
    con.close()


def stats() -> dict:
    con = _conn()
    total = con.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
    fresh = con.execute(
        "SELECT COUNT(*) FROM cache WHERE cached_at > datetime('now', ?)",
        (f"-{CACHE_TTL_HOURS} hours",),
    ).fetchone()[0]
    con.close()
    return {"total_entries": total, "fresh_entries": fresh, "ttl_hours": CACHE_TTL_HOURS}


def clear():
    con = _conn()
    con.execute("DELETE FROM cache")
    con.commit()
    con.close()
