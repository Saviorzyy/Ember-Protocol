"""Ember Protocol — SQLite Persistence"""
from __future__ import annotations
import sqlite3
import json
import os
import time
from typing import Optional

DB_PATH = None  # Set on init


def init_db(path: str):
    global DB_PATH
    DB_PATH = path
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS agents (
            agent_id TEXT PRIMARY KEY,
            agent_name TEXT NOT NULL,
            token_hash TEXT NOT NULL,
            chassis TEXT NOT NULL,
            created_at REAL DEFAULT (strftime('%s', 'now'))
        );
        CREATE TABLE IF NOT EXISTS world_snapshots (
            tick INTEGER PRIMARY KEY,
            timestamp REAL NOT NULL,
            snapshot_data TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS action_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tick INTEGER NOT NULL,
            agent_id TEXT NOT NULL,
            action_type TEXT NOT NULL,
            action_data TEXT NOT NULL,
            result TEXT NOT NULL,
            timestamp REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_action_log_tick ON action_log(tick);
        CREATE INDEX IF NOT EXISTS idx_action_log_agent ON action_log(agent_id);
        CREATE TABLE IF NOT EXISTS wal_log (
            tick INTEGER NOT NULL,
            seq INTEGER NOT NULL,
            change_type TEXT NOT NULL,
            change_data TEXT NOT NULL,
            PRIMARY KEY (tick, seq)
        );
    """)
    conn.commit()
    conn.close()


def get_conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def register_agent(agent_id: str, agent_name: str, token_hash: str, chassis: dict):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO agents (agent_id, agent_name, token_hash, chassis) VALUES (?,?,?,?)",
                 (agent_id, agent_name, token_hash, json.dumps(chassis)))
    conn.commit()
    conn.close()


def verify_token(agent_id: str, token_hash: str) -> bool:
    conn = get_conn()
    row = conn.execute("SELECT token_hash FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
    conn.close()
    return row is not None and row[0] == token_hash


def save_snapshot(tick: int, snapshot_data: dict):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO world_snapshots (tick, timestamp, snapshot_data) VALUES (?,?,?)",
                 (tick, time.time(), json.dumps(snapshot_data)))
    conn.commit()
    conn.close()


def load_latest_snapshot() -> Optional[tuple[int, dict]]:
    conn = get_conn()
    row = conn.execute("SELECT tick, snapshot_data FROM world_snapshots ORDER BY tick DESC LIMIT 1").fetchone()
    conn.close()
    if row:
        return row[0], json.loads(row[1])
    return None


def log_action(tick: int, agent_id: str, action_type: str, action_data: dict, result: dict):
    conn = get_conn()
    conn.execute("INSERT INTO action_log (tick, agent_id, action_type, action_data, result, timestamp) VALUES (?,?,?,?,?,?)",
                 (tick, agent_id, action_type, json.dumps(action_data), json.dumps(result), time.time()))
    conn.commit()
    conn.close()


# ── P-1: WAL (Write-Ahead Log) ──────────────────
def write_wal_entries(tick: int, changes: list[dict]):
    """Write per-tick WAL entries."""
    conn = get_conn()
    for seq, change in enumerate(changes):
        conn.execute(
            "INSERT INTO wal_log (tick, seq, change_type, change_data) VALUES (?,?,?,?)",
            (tick, seq, change.get("type", ""), json.dumps(change))
        )
    conn.commit()
    conn.close()


def read_wal_after(tick: int) -> list[dict]:
    """Read WAL entries after specified tick."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT change_type, change_data FROM wal_log WHERE tick > ? ORDER BY tick, seq",
        (tick,)
    ).fetchall()
    conn.close()
    return [{"type": r[0], **json.loads(r[1])} for r in rows]


def truncate_wal(before_tick: int):
    """Remove WAL entries before specified tick (after snapshot confirmed)."""
    conn = get_conn()
    conn.execute("DELETE FROM wal_log WHERE tick < ?", (before_tick,))
    conn.commit()
    conn.close()
