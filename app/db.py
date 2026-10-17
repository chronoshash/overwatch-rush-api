"""SQLite persistence for self-reported match records.

Deliberately stdlib-only: sqlite3 ships with Python, so there is no new
dependency and no service to run. The database file lives outside the repo
(`var/`, git-ignored) because it contains user data, not project data.

A monotonic `revision` counter is bumped on every write. The HTTP cache layer
includes it in its ETag key, so a cached aggregate can never be revalidated as
"not modified" after a new match was stored.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DB_PATH_ENV = "OWR_DB_PATH"
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "var" / "owr.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    client_match_id  TEXT    UNIQUE,
    player           TEXT    NOT NULL,
    player_key       TEXT    NOT NULL,
    hero             TEXT    NOT NULL,
    mode             TEXT    NOT NULL,
    map              TEXT,
    result           TEXT    NOT NULL CHECK (result IN ('win', 'loss', 'draw')),
    kills            INTEGER NOT NULL DEFAULT 0 CHECK (kills >= 0),
    deaths           INTEGER NOT NULL DEFAULT 0 CHECK (deaths >= 0),
    assists          INTEGER NOT NULL DEFAULT 0 CHECK (assists >= 0),
    damage           INTEGER CHECK (damage IS NULL OR damage >= 0),
    healing          INTEGER CHECK (healing IS NULL OR healing >= 0),
    duration_seconds INTEGER CHECK (duration_seconds IS NULL OR duration_seconds >= 0),
    played_at        TEXT    NOT NULL,
    notes            TEXT    NOT NULL DEFAULT '',
    created_at       TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_matches_player ON matches (player_key, played_at);
CREATE INDEX IF NOT EXISTS idx_matches_hero ON matches (hero);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def db_path() -> Path:
    return Path(os.environ.get(DB_PATH_ENV, DEFAULT_DB_PATH))


def utc_now() -> datetime:
    return datetime.now(UTC)


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Open a short-lived connection; commits on success, rolls back on error."""
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        conn.execute("INSERT OR IGNORE INTO meta (key, value) VALUES ('revision', '0')")


def revision() -> int:
    """Read-only revision counter used for ETag invalidation."""
    try:
        with connect() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key = 'revision'").fetchone()
        return int(row["value"]) if row else 0
    except sqlite3.Error:
        return 0


def _bump_revision(conn: sqlite3.Connection) -> None:
    conn.execute(
        "UPDATE meta SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT) WHERE key = 'revision'"
    )


def normalize_player(player: str) -> tuple[str, str]:
    """Return (display_name, lookup_key). Names are compared case-insensitively."""
    display = " ".join(player.split())
    return display, display.casefold()


# --------------------------------------------------------------------------- #
# Writes
# --------------------------------------------------------------------------- #
def insert_match(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Insert a match. Returns (row, replayed).

    A client-supplied `client_match_id` makes retries idempotent: the second
    POST with the same id returns the stored record instead of a duplicate.
    """
    display, key = normalize_player(payload["player"])
    now = utc_now().isoformat(timespec="seconds")
    played_at = (
        (payload.get("played_at") or utc_now()).astimezone(UTC).isoformat(timespec="seconds")
    )

    with connect() as conn:
        if payload.get("client_match_id"):
            existing = conn.execute(
                "SELECT * FROM matches WHERE client_match_id = ?",
                (payload["client_match_id"],),
            ).fetchone()
            if existing is not None:
                return dict(existing), True

        cursor = conn.execute(
            """
            INSERT INTO matches (
                client_match_id, player, player_key, hero, mode, map, result,
                kills, deaths, assists, damage, healing, duration_seconds,
                played_at, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("client_match_id"),
                display,
                key,
                payload["hero"],
                payload["mode"],
                payload.get("map"),
                payload["result"],
                payload.get("kills", 0),
                payload.get("deaths", 0),
                payload.get("assists", 0),
                payload.get("damage"),
                payload.get("healing"),
                payload.get("duration_seconds"),
                played_at,
                payload.get("notes", ""),
                now,
            ),
        )
        _bump_revision(conn)
        row = conn.execute("SELECT * FROM matches WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return dict(row), False


def delete_match(match_id: int) -> bool:
    with connect() as conn:
        cursor = conn.execute("DELETE FROM matches WHERE id = ?", (match_id,))
        if cursor.rowcount:
            _bump_revision(conn)
        return bool(cursor.rowcount)


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #
def get_match(match_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
    return dict(row) if row else None


def list_matches(
    *,
    player: str | None = None,
    hero: str | None = None,
    mode: str | None = None,
    result: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    clauses: list[str] = []
    params: list[Any] = []
    if player:
        clauses.append("player_key = ?")
        params.append(normalize_player(player)[1])
    if hero:
        clauses.append("hero = ?")
        params.append(hero)
    if mode:
        clauses.append("mode = ?")
        params.append(mode)
    if result:
        clauses.append("result = ?")
        params.append(result)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) AS n FROM matches {where}", params).fetchone()["n"]
        rows = conn.execute(
            f"SELECT * FROM matches {where} ORDER BY played_at DESC, id DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
    return [dict(row) for row in rows], int(total)


def list_players() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT player, player_key, COUNT(*) AS matches,
                   MAX(played_at) AS last_played_at
            FROM matches
            GROUP BY player_key
            ORDER BY matches DESC, player_key ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def player_stats(player: str) -> dict[str, Any] | None:
    """Aggregate one player. Returns None if the player has no matches."""
    key = normalize_player(player)[1]
    with connect() as conn:
        overall = conn.execute(
            """
            SELECT COUNT(*) AS matches,
                   SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) AS wins,
                   SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) AS losses,
                   SUM(CASE WHEN result = 'draw' THEN 1 ELSE 0 END) AS draws,
                   SUM(kills) AS kills, SUM(deaths) AS deaths, SUM(assists) AS assists,
                   SUM(damage) AS damage, SUM(healing) AS healing,
                   AVG(duration_seconds) AS avg_duration,
                   MIN(played_at) AS first_played_at,
                   MAX(played_at) AS last_played_at
            FROM matches WHERE player_key = ?
            """,
            (key,),
        ).fetchone()

        if not overall or not overall["matches"]:
            return None

        by_hero = conn.execute(
            """
            SELECT hero, COUNT(*) AS matches,
                   SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) AS wins,
                   SUM(kills) AS kills, SUM(deaths) AS deaths, SUM(assists) AS assists
            FROM matches WHERE player_key = ?
            GROUP BY hero ORDER BY matches DESC, hero ASC
            """,
            (key,),
        ).fetchall()

        by_mode = conn.execute(
            """
            SELECT mode, COUNT(*) AS matches,
                   SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) AS wins
            FROM matches WHERE player_key = ?
            GROUP BY mode ORDER BY matches DESC, mode ASC
            """,
            (key,),
        ).fetchall()

        display = conn.execute(
            "SELECT player FROM matches WHERE player_key = ? ORDER BY played_at DESC LIMIT 1",
            (key,),
        ).fetchone()["player"]

    kills = int(overall["kills"] or 0)
    deaths = int(overall["deaths"] or 0)
    assists = int(overall["assists"] or 0)
    matches = int(overall["matches"])

    return {
        "player": display,
        "matches": matches,
        "wins": int(overall["wins"] or 0),
        "losses": int(overall["losses"] or 0),
        "draws": int(overall["draws"] or 0),
        "win_rate": _rate(int(overall["wins"] or 0), matches),
        "kills": kills,
        "deaths": deaths,
        "assists": assists,
        "kda": round((kills + assists) / deaths, 3) if deaths else None,
        "kills_per_match": _rate(kills, matches),
        "deaths_per_match": _rate(deaths, matches),
        "avg_duration_seconds": (
            round(float(overall["avg_duration"]), 1)
            if overall["avg_duration"] is not None
            else None
        ),
        "total_damage": int(overall["damage"]) if overall["damage"] is not None else None,
        "total_healing": int(overall["healing"]) if overall["healing"] is not None else None,
        "first_played_at": overall["first_played_at"],
        "last_played_at": overall["last_played_at"],
        "per_hero": [
            {
                "hero": row["hero"],
                "matches": int(row["matches"]),
                "wins": int(row["wins"] or 0),
                "win_rate": _rate(int(row["wins"] or 0), int(row["matches"])),
                "kills": int(row["kills"] or 0),
                "deaths": int(row["deaths"] or 0),
                "assists": int(row["assists"] or 0),
            }
            for row in by_hero
        ],
        "per_mode": [
            {
                "mode": row["mode"],
                "matches": int(row["matches"]),
                "wins": int(row["wins"] or 0),
                "win_rate": _rate(int(row["wins"] or 0), int(row["matches"])),
            }
            for row in by_mode
        ],
    }
